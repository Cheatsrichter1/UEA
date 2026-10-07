"""Run the token task set: python -m bench [task ...] [--write].

Counts tokens with tiktoken (o200k_base). That is OpenAI's tokenizer; Claude tokenizes
differently, so absolute numbers are approximate and the comparison between versions is what
matters.
"""

import contextlib
import io
import shlex
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from bench.tasks import HELP, ROOT, TASKS, Step, Task, prepare
from uea.cli import main as uea
from uea.project import Project

RESULTS = ROOT / "bench" / "results.md"


def tokenizer() -> Callable[[str], int]:
    try:
        import tiktoken
    except ImportError:  # pragma: no cover
        sys.exit("bench needs tiktoken: uv sync (it is in the dev group)")
    enc = tiktoken.get_encoding("o200k_base")
    return lambda s: len(enc.encode(s))


def shell_text(step: Step) -> str:
    """The step as an agent types it in a shell."""
    cmd = shlex.join(["uea", *step.args])
    if step.stdin is None:
        return cmd
    return f"{cmd} <<'EOF'\n{step.stdin}EOF"


def call(root: Path, step: Step) -> tuple[int, str]:
    buf = io.StringIO()
    old_stdin = sys.stdin
    if step.stdin is not None:
        sys.stdin = io.StringIO(step.stdin)
    try:
        with contextlib.redirect_stdout(buf):
            code = uea(["-C", str(root), *step.args])
    finally:
        sys.stdin = old_stdin
    return code, buf.getvalue()


def run_steps(root: Path, steps: list[Step]) -> list[tuple[Step, int, str]]:
    return [(s, *call(root, s)) for s in steps]


@dataclass
class TaskResult:
    task: Task
    tokens_in: int
    tokens_out: int
    steps: int
    failed_steps: int
    problems: list[str]
    transcript: str

    @property
    def total(self) -> int:
        return self.tokens_in + self.tokens_out


def run_task(task: Task, count: Callable[[str], int]) -> TaskResult:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "p"
        Project.init(root)
        prepare(task, root, run_steps)
        if task.setup is not None:
            call(root, Step(["log", "1"]))  # record a copied house as its first batch
        results = run_steps(root, task.steps)
        tin = sum(count(shell_text(s)) for s, _, _ in results)
        tout = sum(count(out) for _, _, out in results)
        failed = sum(1 for _, code, _ in results if code != 0)
        problems = task.check(Project(root))
        transcript = "\n".join(f"$ {shell_text(s)}\n{out}" for s, _, out in results)
        return TaskResult(task, tin, tout, len(results), failed, problems, transcript)


def help_tokens(count: Callable[[str], int]) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        return sum(count(call(Path(tmp), Step(args))[1]) for args in HELP)


def table(results: list[TaskResult], help_n: int) -> str:
    lines = [
        "| Task | Steps | Tokens in | Tokens out | Total | Check |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in results:
        ok = "ok" if not r.problems and not r.failed_steps else "FAILED: " + "; ".join(r.problems)
        lines.append(
            f"| {r.task.id} | {r.steps} | {r.tokens_in:,} | {r.tokens_out:,} | {r.total:,} | {ok} |"
        )
    total = sum(r.total for r in results)
    lines.append(f"| **all** | | | | **{total:,}** | |")
    lines.append("")
    lines.append(
        f"Reading the help once (`{'`, `'.join(' '.join(h) for h in HELP)}`): {help_n:,} tokens."
    )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    write = "--write" in argv
    names = [a for a in argv if not a.startswith("--")]
    tasks = [t for t in TASKS if not names or t.id in names]
    count = tokenizer()
    results = [run_task(t, count) for t in tasks]
    text = table(results, help_tokens(count))
    print(text)
    if "--transcripts" in argv:
        for r in results:
            print(f"\n## {r.task.id}\n\n{r.transcript}")
    if write:
        RESULTS.write_text(
            "# Token task set: results\n\n"
            "Reference solutions run through the real CLI (`uv run python -m bench --write`)."
            " Tokens counted with tiktoken o200k_base: commands and operations typed (in),"
            " UEA's output read (out). Agent runs, which add the error rate, are not wired"
            " up yet.\n\n" + text + "\n",
            encoding="utf-8",
        )
    return 0 if all(not r.problems and not r.failed_steps for r in results) else 1
