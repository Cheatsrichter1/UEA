"""The `uea` command line. Terse text by default, --json for programs."""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from uea import __version__
from uea.batch import Result, revert, run, sync
from uea.core.issues import Issue
from uea.core.model import Model
from uea.core.registry import natural
from uea.core.schema import Element, fmt_value, spec
from uea.core.values import Ref, RefList
from uea.derive import Derived, Report, report
from uea.fmt import ar, ids
from uea.help import TOPICS, help_text
from uea.project import LoadError, NotAProject, Project

FIND_LIMIT = 60


class Parser(argparse.ArgumentParser):
    def __init__(self, *args: Any, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.commands: dict[str, Parser] = {}
        """The subcommands, for docs/reference.md."""

    def error(self, message: str) -> NoReturn:
        sys.stderr.write(f"uea: {message}. See: uea help\n")
        raise SystemExit(2)


def out(lines: str | Sequence[str]) -> None:
    text = lines if isinstance(lines, str) else "\n".join(lines)
    if text:
        print(text)


def out_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


class Ctx:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.json: bool = bool(args.json)
        self.dir = Path(args.C) if args.C else Path.cwd()
        self._project: Project | None = None
        self._model: Model | None = None
        self._d: Derived | None = None
        self._rep: Report | None = None
        self.note: str | None = None

    @property
    def project(self) -> Project:
        if self._project is None:
            self._project = Project.find(self.dir)
            with self._project.lock():
                self.note = sync(self._project)
            if self.note and not self.json:
                out(self.note)
        return self._project

    @property
    def model(self) -> Model:
        if self._model is None:
            self._model = self.project.load()
        return self._model

    def derived(self) -> tuple[Derived, Report]:
        if self._d is None or self._rep is None:
            self._d, self._rep = report(self.model)
        return self._d, self._rep


# ---------- formatting ----------


def describe(d: Derived, el: Element) -> list[str]:
    pack = d.model.reg.packs[type(el).pack]
    out: list[str] = []
    for p in d.model.reg.packs.values():
        if (p.describe is not None and (p is pack or el.kind in p.also)) or (
            p.describe is not None and el.kind in ("level", "grid") and not out
        ):
            out += p.describe(d, el)
    return out


def issue_lines(issues: Sequence[Issue], prefix: str = "") -> list[str]:
    return [prefix + i.text() for i in issues]


def element_view(d: Derived, rep: Report, el: Element) -> list[str]:
    lines = [el.line(), *(" " + x for x in describe(d, el))]
    lines += [" ! " + i.text() for i in rep.issues if i.el == el.id]
    lines += [" ~ waived " + i.code + f" ({w.id})" for i, w in rep.waived if i.el == el.id]
    lines += [
        f' ? {r.id} from {r.disc}: "{r.label}"' for r in rep.requests if el.id in r.targets.refs()
    ]
    return lines


def element_json(d: Derived, rep: Report, el: Element) -> dict[str, Any]:
    return {
        "id": el.id,
        "kind": el.kind,
        "line": el.line(),
        "fields": el.model_dump(exclude_none=True),
        "derived": describe(d, el),
        "issues": [i.as_dict() for i in rep.issues if i.el == el.id],
    }


def added_text(res: Result) -> str:
    assert res.applied is not None
    model_added = res.applied.added
    parts: list[str] = []
    run_: list[str] = []
    for ph, key in model_added:
        if not any(ch.isdigit() for ch in key) or key[0].isupper():
            continue  # named elements: the agent knows their names
        if ph is None:
            run_.append(key)
            continue
        if run_:
            parts.append(ids(run_, 100))
            run_ = []
        parts.append(f"{ph}={key}")
    if run_:
        parts.append(ids(run_, 100))
    return " ".join(parts)


def result_lines(res: Result, rep_owner: Report | None) -> list[str]:
    if res.errors:
        return ["rejected, nothing changed:", *res.errors]
    if not res.ok:
        packs = sorted({rep_owner.owner(i) for i in res.rejected}) if rep_owner else []
        n = len(res.rejected)
        head = (
            f"rejected: {n} new error{'s' if n > 1 else ''} in {', '.join(packs)}. Nothing changed."
        )
        return [head, *issue_lines(res.rejected)]
    a = res.applied
    assert a is not None
    if not a.ops:
        return ["ok: nothing changed"]
    after = res.after
    counts: list[str] = []
    if a.added:
        counts.append(f"+{len(a.added)}")
    if a.changed:
        counts.append(f"{len(a.changed)} changed ({ids(a.changed)})")
    if a.removed:
        counts.append(f"-{len(a.removed)} ({ids(a.removed)})")
    if a.closed:
        counts.append(f"done {' '.join(a.closed)}")
    packs = ", ".join(p for p in a.model.reg.packs if p in a.packs)
    if res.dry:
        head = f"ok (dry run, nothing written) ({packs}): {' · '.join(counts)}"
    elif res.revert is not None:
        head = f"ok batch {res.batch} ({packs}): reverted {res.revert} · {' · '.join(counts)}"
    else:
        head = f"ok batch {res.batch} ({packs}): {' · '.join(counts)}"
    lines = [head]
    added = added_text(res)
    if added:
        lines.append(" " + added)
    m = a.model
    new_ids = {k for _, k in a.added}
    notes = derived_notes(res.derived, new_ids) if res.derived is not None else []
    lines += notes
    if after is not None:
        written = a.packs
        mine = [i for i in res.new_issues if after.owner(i) in written]
        other = [i for i in res.new_issues if after.owner(i) not in written]
        lines += issue_lines(mine, "new: ")
        by_pack: dict[str, list[Issue]] = {}
        for i in other:
            by_pack.setdefault(after.owner(i), []).append(i)
        for p, items in by_pack.items():
            lines += [f"affects {p}: {i.text()}" for i in items]
        fixed: dict[str, list[str]] = {}
        for i in res.fixed:
            fixed.setdefault(after.owner(i) if i.el in m else "-", []).append(f"{i.code} {i.el}")
        for p, items in fixed.items():
            lines.append(f"fixed{'' if p in written else ' ' + p}: {' · '.join(items)}")
        if res.opened:
            owners: dict[str, list[str]] = {}
            for r in after.requests:
                if r.id in res.opened:
                    owners.setdefault(after.request_owner(r), []).append(r.id)
            for p, items in owners.items():
                lines.append(f"open for {p}: {' '.join(items)}")
    if res.follows:
        by: dict[str, list[str]] = {}
        for k in res.follows:
            if k in m:
                by.setdefault(type(m[k]).pack, []).append(k)
        lines.append("follows: " + " · ".join(f"{ids(v)} ({p})" for p, v in by.items()))
    return lines


def derived_notes(d: Derived, new_ids: set[str]) -> list[str]:
    """Key derived values of new rooms and stairs, so the agent sees them at once."""
    g = d.arch
    lines: list[str] = []
    rooms = [g.rooms[k] for k in sorted(new_ids, key=natural) if k in g.rooms]
    if rooms:
        lines.append(" ".join(f"{r.id} {ar(r.area_fin)}" for r in rooms) + " m² fin")
    for k in sorted(new_ids, key=natural):
        s = g.stairs.get(k)
        if s is not None:
            lines.append(
                f"{s.id}: {s.n} risers {s.riser:.3f}, tread {s.tread:g}, 2h+a {s.step:.3f}"
            )
    return lines


def result_json(res: Result) -> dict[str, Any]:
    a = res.applied
    return {
        "ok": res.ok,
        "batch": res.batch,
        "dry": res.dry,
        "errors": res.errors,
        "rejected": [i.as_dict() for i in res.rejected],
        "added": [{"placeholder": p, "id": k} for p, k in (a.added if a else [])],
        "changed": a.changed if a else [],
        "removed": a.removed if a else [],
        "new_issues": [i.as_dict() for i in res.new_issues],
        "fixed": [i.as_dict() for i in res.fixed],
        "follows": res.follows,
        "external": res.external,
    }


# ---------- commands ----------


def cmd_help(ctx: Ctx) -> int:
    from uea.packs import default_registry

    topic: str | None = ctx.args.topic
    text = help_text(default_registry(), topic)
    if text is None:
        out(f"no help for {topic!r}. Topics: {TOPICS}")
        return 1
    out(text.rstrip())
    return 0


def cmd_init(ctx: Ctx) -> int:
    root = ctx.dir / ctx.args.dir
    try:
        Project.init(root)
    except FileExistsError as e:
        out(f"uea: {e}")
        return 1
    out(f"ok project {ctx.args.dir}: empty. Next: uea help start")
    return 0


def _scope_level(m: Model, scope: str) -> str | None:
    el = m.get(scope)
    return scope if el is not None and el.kind == "level" else None


def cmd_show(ctx: Ctx) -> int:
    from uea.packs.arch.views import level_of, level_summary

    m = ctx.model
    d, rep = ctx.derived()
    scope: str | None = ctx.args.scope
    if scope and scope in m and m[scope].kind != "level":
        el = m[scope]
        if ctx.json:
            out_json(element_json(d, rep, el))
        else:
            out(element_view(d, rep, el))
        return 0
    pack: str | None = None
    level: str | None = None
    if scope and ":" in scope:
        pack, level = scope.split(":", 1)
    elif scope and scope in m.reg.packs:
        pack = scope
    elif scope and scope != "project":
        level = _scope_level(m, scope)
        if level is None:
            out(
                f"unknown scope {scope!r}: use project, a level,"
                f" a discipline ({' '.join(m.reg.packs)}) or an id"
            )
            return 1
    if level is not None and level not in d.arch.levels:
        out(f"unknown level {level!r}")
        return 1
    lines: list[str] = []
    if pack is None and level is None:
        proj = m.of_kind("project")
        head = proj[0].line().replace("project ", "", 1) if proj else "(no project line yet)"
        lines.append(f"{head} · batch {ctx.project.history.last()} · {len(m)} elements")
        for lv in d.arch.level_order():
            lines += level_summary(d, lv)
        per = {p: len(m.in_pack(p)) for p in m.reg.packs if m.in_pack(p)}
        lines.append(" · ".join(f"{p} {n}" for p, n in per.items()))
    elif level is not None and pack in (None, "arch"):
        lines += level_summary(d, level)
    else:
        assert pack is not None
        if pack not in m.reg.packs:
            out(f"unknown discipline {pack!r}: {' '.join(m.reg.packs)}")
            return 1
        els = [e for e in m.in_pack(pack) if level is None or level_of(d, e) == level]
        counts: dict[str, int] = {}
        for e in els:
            k = f"type {e.category}" if e.kind == "type" else e.kind
            counts[k] = counts.get(k, 0) + 1
        lines.append(
            f"{pack}{':' + level if level else ''}: "
            + " · ".join(f"{n} {k}" for k, n in counts.items())
        )
    issues = rep.of(pack) if pack else rep.issues
    if level is not None:
        issues = [
            i for i in issues if i.el == level or (i.el in m and level_of(d, m[i.el]) == level)
        ]
    errs = sum(1 for i in issues if i.severity == "error")
    reqs = [r for r in rep.requests if pack is None or rep.request_owner(r) == pack]
    lines.append(
        f"issues {errs} errors {len(issues) - errs} warnings · requests {len(reqs)} open"
        + (f" · waived {len(rep.waived)}" if rep.waived and pack in (None, "issues") else "")
        + (" (uea check)" if issues or reqs else "")
    )
    if ctx.json:
        out_json({"lines": lines})
    else:
        out(lines)
    return 0


def cmd_get(ctx: Ctx) -> int:
    m = ctx.model
    d, rep = ctx.derived()
    missing = [k for k in ctx.args.ids if k not in m]
    found = [m[k] for k in ctx.args.ids if k in m]
    if ctx.json:
        out_json({"elements": [element_json(d, rep, e) for e in found], "missing": missing})
    else:
        for e in found:
            out(element_view(d, rep, e))
        if missing:
            out(f"not found: {' '.join(missing)}")
    return 1 if missing else 0


def _matches(d: Derived, el: Element, flt: list[str]) -> bool:
    from uea.packs.arch.views import in_room, level_of

    sp = spec(type(el))
    for f in flt:
        if "=" in f:
            k, v = f.split("=", 1)
            if k == "level":
                if level_of(d, el) != v:
                    return False
                continue
            if k == "room":
                if not in_room(d, el, v):
                    return False
                continue
            if k not in sp.fields:
                return False
            val = getattr(el, k)
            if isinstance(val, Ref):
                if v not in (val.id, val.fmt()):
                    return False
            elif isinstance(val, RefList):
                if v not in val.refs():
                    return False
            elif val is None or fmt_value(val).strip('"') != v:
                return False
        else:
            if f in ("ext", "int") and el.kind == "wall":
                w = d.arch.walls.get(el.id)
                if w is None or (w.ext is not None) != (f == "ext"):
                    return False
                continue
            if f == "open" and el.kind == "req":
                if not getattr(el, "open", False):
                    return False
                continue
            if f in sp.flags:
                if not getattr(el, f):
                    return False
                continue
            hit = any(getattr(el, n) == f for n in sp.flag_enums)
            if not hit and el.category != f:
                return False
    return True


def cmd_find(ctx: Ctx) -> int:
    m = ctx.model
    d, _ = ctx.derived()
    kind: str = ctx.args.kind
    if kind not in ("all", "type") and kind not in m.reg.kinds:
        out(f"unknown kind {kind!r}. Kinds: {' '.join(m.reg.kind_names())} all")
        return 1
    els = m.sorted() if kind == "all" else m.of_kind(kind)
    hits = [e for e in els if _matches(d, e, ctx.args.filters)]
    skip: int = ctx.args.skip
    page = hits[skip : skip + FIND_LIMIT]
    if ctx.json:
        out_json({"total": len(hits), "elements": [e.line() for e in page]})
        return 0
    if ctx.args.ids:
        out(ids([e.id for e in page], 1000))
    else:
        out([e.line() for e in page])
    if not hits:
        out("none")
    rest = len(hits) - skip - len(page)
    if rest > 0:
        out(f"… {rest} more: add --skip {skip + len(page)}")
    return 0


def _read_ops(ctx: Ctx) -> str | None:
    if ctx.args.file:
        return Path(ctx.args.file).read_text(encoding="utf-8")
    if sys.stdin.isatty():
        out("uea apply: pipe the operations in, e.g. uea apply --by me -m why <<'EOF' ... EOF")
        return None
    return sys.stdin.read()


def _by(ctx: Ctx) -> str | None:
    by: str | None = ctx.args.by or os.environ.get("UEA_BY")
    if not by:
        out("uea: say who makes the change: --by <who> (or set UEA_BY)")
    return by


def _print_result(ctx: Ctx, res: Result) -> int:
    if ctx.json:
        out_json(result_json(res))
    else:
        if res.external:
            out(res.external)
        out(result_lines(res, res.after))
    return 0 if res.ok else 1


def cmd_apply(ctx: Ctx) -> int:
    by = _by(ctx)
    if by is None:
        return 2
    if not ctx.args.m:
        out('uea: say why: -m "message" (it goes into the history for the human)')
        return 2
    text = _read_ops(ctx)
    if text is None:
        return 2
    res = run(ctx.project, text, by, ctx.args.m, dry=ctx.args.dry_run)
    return _print_result(ctx, res)


def cmd_revert(ctx: Ctx) -> int:
    by = _by(ctx)
    if by is None:
        return 2
    res = revert(ctx.project, ctx.args.batch, by, ctx.args.m)
    return _print_result(ctx, res)


def cmd_check(ctx: Ctx) -> int:
    m = ctx.model
    _, rep = ctx.derived()
    disc: str | None = ctx.args.discipline
    if disc is not None and disc not in m.reg.packs:
        out(f"unknown discipline {disc!r}: {' '.join(m.reg.packs)}")
        return 1
    issues = rep.of(disc)
    reqs = [
        r for r in rep.requests if disc is None or rep.request_owner(r) == disc or r.disc == disc
    ]
    waived = [(i, w) for i, w in rep.waived if disc is None or rep.owner(i) == disc]
    errs = [i for i in issues if i.severity == "error"]
    warns = [i for i in issues if i.severity == "warning"]
    if ctx.json:
        out_json(
            {
                "errors": [i.as_dict() for i in errs],
                "warnings": [i.as_dict() for i in warns],
                "requests": [
                    {
                        "id": r.id,
                        "from": r.disc,
                        "to": rep.request_owner(r),
                        "targets": list(r.targets.refs()),
                        "text": r.label,
                    }
                    for r in reqs
                ],
                "waived": [
                    {"code": i.code, "el": i.el, "waiver": w.id, "by": w.by} for i, w in waived
                ],
            }
        )
        return 1 if errs else 0
    lines = [
        f"{len(errs)} errors · {len(warns)} warnings · requests {len(reqs)} open"
        f" · waived {len(waived)}"
    ]
    lines += issue_lines(errs) + issue_lines(warns)
    for r in reqs:
        lines.append(f'{r.id} {r.disc}→{rep.request_owner(r)} {r.targets.fmt()}: "{r.label}"')
    if any(disc is None or rep.request_owner(r) == disc for r in reqs):
        lines.append('close: ~ <q> done · reject: ~ <q> rejected="reason"')
    for i, w in waived:
        lines.append(
            f'waived: {i.code} {i.el} ({w.id}{", by " + w.by if w.by else ""}: "{w.label}")'
        )
    out(lines)
    return 1 if errs else 0


def cmd_log(ctx: Ctx) -> int:
    entries = ctx.project.history.entries()[-ctx.args.n :]
    if ctx.json:
        out_json({"batches": [json.loads(e.to_json()) for e in entries]})
        return 0
    lines: list[str] = []
    for e in reversed(entries):
        lines.append(f"{e.batch} {e.by}  {e.msg}  {ops_summary(e.ops)}")
    out(lines or "no batches yet")
    return 0


def ops_summary(ops: list[str]) -> str:
    plus: list[str] = []
    change: list[str] = []
    minus: list[str] = []
    for o in ops:
        parts = o.split()
        if o.startswith("+") and len(parts) > 2:
            plus.append(parts[2])
        elif o.startswith(">") and len(parts) > 2:
            change.append(parts[2])
        elif o.startswith("~"):
            change.append(parts[1])
        elif o.startswith("-"):
            minus.extend(parts[1:])
    out: list[str] = []
    if plus:
        out.append("+" + ids(plus, 8))
    if change:
        out.append("~" + ids(change, 8))
    if minus:
        out.append("-" + ids(minus, 8))
    return " ".join(out)


def cmd_calc(ctx: Ctx) -> int:
    from uea.calc import run_calc

    return run_calc(ctx, out, out_json)


def cmd_data(ctx: Ctx) -> int:
    from uea.calc.cli import run_data

    return run_data(ctx, out, out_json)


def cmd_render(ctx: Ctx) -> int:
    from uea.export.cli import render

    return render(ctx, out)


def cmd_export(ctx: Ctx) -> int:
    from uea.export.cli import export

    return export(ctx, out)


def cmd_import(ctx: Ctx) -> int:
    from uea.importer.cli import run_import

    by = _by(ctx)
    if by is None:
        return 2
    return run_import(ctx, by, out, out_json, issue_lines, result_json)


def cmd_version(ctx: Ctx) -> int:
    out(f"uea {__version__}")
    return 0


def build_parser() -> Parser:
    p = Parser(prog="uea", add_help=False, description="UEA. See: uea help")
    p.add_argument("-C", metavar="DIR", help="run in DIR")
    p.add_argument("--json", action="store_true")
    p.add_argument("--version", action="store_true")
    sub = p.add_subparsers(dest="cmd", parser_class=Parser)

    def add(name: str, fn: Any, **kw: Any) -> Parser:
        sp: Parser = sub.add_parser(name, add_help=False, **kw)
        sp.add_argument("-C", metavar="DIR", default=argparse.SUPPRESS)
        sp.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        sp.set_defaults(func=fn)
        p.commands[name] = sp
        return sp

    add("help", cmd_help).add_argument("topic", nargs="?")
    add("version", cmd_version)
    add("init", cmd_init).add_argument("dir")
    add("show", cmd_show).add_argument("scope", nargs="?")
    add("get", cmd_get).add_argument("ids", nargs="+", metavar="id")
    f = add("find", cmd_find)
    f.add_argument("kind")
    f.add_argument("filters", nargs="*")
    f.add_argument("--skip", type=int, default=0, metavar="N")
    f.add_argument("--ids", action="store_true")
    a = add("apply", cmd_apply)
    a.add_argument("--by", metavar="WHO")
    a.add_argument("-m", metavar="WHY")
    a.add_argument("-f", "--file")
    a.add_argument("--dry-run", action="store_true")
    r = add("revert", cmd_revert)
    r.add_argument("batch", type=int)
    r.add_argument("--by", metavar="WHO")
    r.add_argument("-m", metavar="WHY")
    add("check", cmd_check).add_argument("discipline", nargs="?")
    add("log", cmd_log).add_argument("n", nargs="?", type=int, default=10)
    c = add("calc", cmd_calc)
    c.add_argument("name", nargs="?")
    c.add_argument("rest", nargs="*", metavar="scope|name=value")
    dt = add("data", cmd_data)
    dt.add_argument("action", nargs="?")
    dt.add_argument("rest", nargs="*")
    dt.add_argument("--edition", metavar="E")
    dt.add_argument("--source", metavar="S", default="")
    rd = add("render", cmd_render)
    rd.add_argument("scope")
    rd.add_argument("view", nargs="?")
    rd.add_argument("-o", "--out", metavar="FILE")
    ex = add("export", cmd_export)
    ex.add_argument("format")
    ex.add_argument("scope", nargs="?")
    ex.add_argument("-o", "--out", metavar="FILE")
    im = add("import", cmd_import)
    im.add_argument("format")
    im.add_argument("file")
    im.add_argument("--by", metavar="WHO")
    im.add_argument("-m", metavar="WHY")
    im.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    if args.version:
        out(f"uea {__version__}")
        return 0
    if getattr(args, "cmd", None) is None:
        args.topic = None
        args.func = cmd_help
    ctx = Ctx(args)
    try:
        return int(args.func(ctx))
    except NotAProject as e:
        out(f"uea: {e}")
        return 2
    except LoadError as e:
        out(
            [
                "uea: the project files have errors; fix them first"
                " (UEA changes nothing until then):",
                *e.errors,
            ]
        )
        return 2
