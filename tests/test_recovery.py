import time

import pytest

from uga.core.contracts import TaskSpec
from uga.memory.store import Store
from uga.orchestrator.jobs import Orchestrator


def wait(jobs, identity):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        row = jobs.store.task(identity)
        if row["status"] not in ("queued", "running"):
            return row
        time.sleep(0.025)
    raise AssertionError("recovery did not finish")


@pytest.mark.integration
def test_crashed_reference_worker_is_recovered_once(tmp_path):
    with Orchestrator(tmp_path, recovery_limit=1) as jobs:
        task = TaskSpec(agent="player", operation="play")
        jobs.submit(task)
        with jobs._lock:
            jobs._tick()
            run = jobs.running[task.task_id]
            run.process.kill()
            run.process.join(1)
        row = wait(jobs, task.task_id)
        assert row["status"] == "succeeded", row
        assert jobs.attempts[task.task_id] == 1
        assert any(event["event"] == "recovering" for event in jobs.store.events(task.task_id))


def test_stale_jobs_are_diagnosed_on_restart(tmp_path):
    store = Store(tmp_path)
    task = TaskSpec(agent="player", operation="play")
    store.create_task(task)
    with Orchestrator(tmp_path) as jobs:
        row = jobs.store.task(task.task_id)
        assert row["status"] == "failed" and "previous process shutdown" in row["error"]


def test_worker_resource_budget_is_enforced(tmp_path):
    with Orchestrator(tmp_path, memory_limit_mb=1) as jobs:
        task = TaskSpec(agent="player", operation="soak", parameters={"seconds": 60})
        jobs.submit(task)
        row = wait(jobs, task.task_id)
        assert row["status"] == "failed" and row["error"] == "memory_limit"
