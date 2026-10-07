"""Atomic batches, revert and the detection of edits made outside UEA.

A batch applies to a copy, is validated, and is rejected if it adds an error in a discipline
it writes. Errors it causes in other disciplines are reported, not blocking (ARCHITECTURE.md §5).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from uea.core.issues import Issue
from uea.core.model import Model
from uea.core.ops import Applied, OpsError, apply_ops, parse_ops
from uea.derive import Derived, Report, report
from uea.project import Entry, Project


@dataclass
class Result:
    ok: bool
    batch: int | None = None
    applied: Applied | None = None
    rejected: list[Issue] = field(default_factory=list[Issue])
    errors: list[str] = field(default_factory=list[str])
    new_issues: list[Issue] = field(default_factory=list[Issue])
    fixed: list[Issue] = field(default_factory=list[Issue])
    follows: list[str] = field(default_factory=list[str])
    opened: list[str] = field(default_factory=list[str])
    external: str | None = None
    revert: int | None = None
    dry: bool = False
    after: Report | None = None
    derived: Derived | None = None
    notes: list[str] = field(default_factory=list[str])


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def replay(project: Project) -> Model:
    """The model as the history describes it."""
    model = Model(project.reg)
    for e in project.history.entries():
        if e.ops:
            apply_ops(model, parse_ops("\n".join(e.ops)), batch=e.batch, internal=True)
    return model


def diff(old: Model, new: Model) -> tuple[list[str], list[str], list[str]]:
    """Ops that turn old into new, their inverse, and the ids added."""
    ops: list[str] = []
    inverse: list[str] = []
    added: list[str] = []
    for el in new.sorted():
        prev = old.get(el.id)
        if prev is None:
            ops.append(f"+ {el.line()}")
            inverse.append(f"- {el.id}")
            added.append(el.id)
        elif prev != el:
            ops.append(f"> {el.line()}")
            inverse.append(f"> {prev.line()}")
    for el in old.sorted():
        if el.id not in new:
            ops.append(f"- {el.id}")
            inverse.append(f"+ {el.line()}")
    inverse.reverse()
    return ops, inverse, added


def sync(project: Project) -> str | None:
    """Record edits made outside UEA as an external batch. Call with the lock held."""
    known = project.history.known_hashes()
    current = project.hashes()
    changed = sorted(f for f in set(known) | set(current) if known.get(f, "") != current.get(f, ""))
    if not changed:
        return None
    now_model = project.load()
    then_model = replay(project)
    ops, inverse, added = diff(then_model, now_model)
    batch = project.history.last() + 1
    files = {f: current.get(f, "") for f in changed}
    project.history.append(
        Entry(
            batch,
            now(),
            "external",
            f"edited outside UEA: {', '.join(changed)}",
            ops,
            inverse,
            ids=[i for i in added if now_model[i].prefix is not None],
            files=files,
            external=True,
        )
    )
    counts = summary_counts(ops)
    return f"external edit recorded as batch {batch} ({', '.join(changed)}): {counts}"


def summary_counts(ops: list[str]) -> str:
    plus = sum(1 for o in ops if o.startswith("+"))
    minus = sum(len(o.split()) - 1 for o in ops if o.startswith("-"))
    change = sum(1 for o in ops if o[0] in "~>")
    parts = [
        f"+{plus}" if plus else "",
        f"{change} changed" if change else "",
        f"-{minus}" if minus else "",
    ]
    return " ".join(p for p in parts if p) or "no changes"


def signatures(rep_d: Any) -> dict[str, tuple[Any, ...]]:
    out: dict[str, tuple[Any, ...]] = {}
    for pack in rep_d.model.reg.packs.values():
        sig = getattr(pack, "signatures", None)
        if sig is not None:
            out.update(sig(rep_d))
    return out


def run(
    project: Project,
    text: str,
    by: str,
    msg: str,
    *,
    dry: bool = False,
    revert: int | None = None,
) -> Result:
    with project.lock():
        external = sync(project)
        model = project.load()
        try:
            ops = parse_ops(text)
        except OpsError as e:
            return Result(False, errors=e.errors, external=external)
        batch = project.history.last() + 1
        work = model.copy()
        try:
            applied = apply_ops(
                work,
                ops,
                batch=batch,
                history_max=project.history.max_ids(),
                internal=revert is not None,
            )
        except OpsError as e:
            return Result(False, errors=e.errors, external=external)
        if not applied.ops:
            return Result(True, None, applied, external=external, notes=["nothing changed"])
        d_before, before = report(model)
        d_after, after = report(work)
        before_keys = {i.key for i in before.issues}
        after_keys = {i.key for i in after.issues}
        written = applied.packs
        rejected = [
            i for i in after.errors() if i.key not in before_keys and after.owner(i) in written
        ]
        if rejected:
            return Result(False, applied=applied, rejected=rejected, external=external, after=after)
        new_issues = [i for i in after.issues if i.key not in before_keys]
        fixed = [i for i in before.issues if i.key not in after_keys]
        sb, sa = signatures(d_before), signatures(d_after)
        touched = applied.touched
        follows = [k for k, v in sa.items() if k not in touched and k in sb and sb[k] != v]
        added_ids = {i for _, i in applied.added}
        opened = [r.id for r in after.requests if r.id in added_ids]
        res = Result(
            True,
            batch,
            applied,
            new_issues=new_issues,
            fixed=fixed,
            follows=follows,
            opened=opened,
            external=external,
            revert=revert,
            dry=dry,
            after=after,
            derived=d_after,
        )
        if dry:
            res.batch = None
            return res
        hashes = project.write(work, written)
        project.history.append(
            Entry(
                batch,
                now(),
                by,
                msg,
                applied.ops,
                applied.inverse,
                ids=[i for _, i in applied.added if work[i].prefix is not None],
                files=hashes,
                revert=revert,
            )
        )
        return res


def revert(project: Project, batch: int, by: str, msg: str | None = None) -> Result:
    with project.lock():
        sync(project)
        entry = project.history.get(batch)
    if entry is None:
        return Result(False, errors=[f"there is no batch {batch}. See uea log"])
    if not entry.inverse:
        return Result(False, errors=[f"batch {batch} changed nothing"])
    mine = entry.touched()
    for later in project.history.entries():
        if later.batch <= batch:
            continue
        clash = sorted(mine & later.touched())
        if clash:
            return Result(
                False,
                errors=[
                    f"batch {later.batch} changed {' '.join(clash)} after batch {batch}."
                    f" Revert {later.batch} first, or change them with a new batch"
                ],
            )
    message = f"revert {batch}: {msg or entry.msg}"
    return run(project, "\n".join(entry.inverse), by, message, revert=batch)
