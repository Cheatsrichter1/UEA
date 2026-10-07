"""Every task of the token task set runs and passes its check (tokens are not counted here)."""

import pytest

from bench.run import run_task
from bench.tasks import TASKS, Task


@pytest.mark.parametrize("task", TASKS, ids=[t.id for t in TASKS])
def test_task(task: Task) -> None:
    r = run_task(task, len)
    assert r.failed_steps == 0, r.transcript
    assert r.problems == [], r.transcript
