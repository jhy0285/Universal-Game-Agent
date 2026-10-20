import os
import time

import pytest

from uga.core.contracts import TaskSpec, TaskStatus
from uga.core.errors import AuthorizationRequired, UGAError
from uga.orchestrator.jobs import Orchestrator
from uga.supervisor.health import Watchdog


def wait_job(jobs, task_id, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = jobs.store.task(task_id)
        if row["status"] not in ("queued", "running"):
            return row
        time.sleep(0.025)
    raise AssertionError(f"job did not finish: {jobs.store.task(task_id)}")


@pytest.mark.integration
def test_spawn_player_result_and_persisted_events(tmp_path):
    with Orchestrator(tmp_path) as jobs:
        spec = TaskSpec(agent="player", operation="play")
        jobs.submit(spec)
        result = wait_job(jobs, spec.task_id)
        assert result["status"] == TaskStatus.SUCCEEDED, result
        assert result["result"]["success"]
        assert jobs.store.events(spec.task_id)[-1]["event"] == "succeeded"
        assert jobs.store.load_checkpoint(spec.task_id)["tick"] >= 0
        with pytest.raises(UGAError):
            Orchestrator(tmp_path)


def test_timeout_cancel_and_unknown_operations(tmp_path):
    with Orchestrator(tmp_path, max_workers=1) as jobs:
        spec = TaskSpec(
            agent="player", operation="soak", parameters={"seconds": 60}, timeout_s=0.01
        )
        jobs.submit(spec)
        assert wait_job(jobs, spec.task_id)["status"] == TaskStatus.TIMED_OUT
        spec = TaskSpec(agent="player", operation="soak", parameters={"seconds": 60})
        jobs.submit(spec)
        assert jobs.cancel(spec.task_id)["status"] == TaskStatus.CANCELLED
        with pytest.raises(ValueError):
            jobs.submit(TaskSpec(agent="player", operation="run_shell"))
        with pytest.raises(AuthorizationRequired):
            jobs.submit(TaskSpec(agent="reverse", operation="analyze", parameters={"path": "x"}))


def test_watchdog_checks_roles_separately_and_stale_heartbeats():
    watchdog = Watchdog(heartbeat_timeout_s=1)
    watchdog.register("game", os.getpid())
    watchdog.register("inference", os.getpid())
    now = time.monotonic()
    watchdog.heartbeat("game", now=now)
    watchdog.heartbeat("inference", now=now - 2)
    health = watchdog.inspect(now=now)
    assert health["game"]["healthy"]
    assert health["inference"]["reason"] == "heartbeat_timeout"
