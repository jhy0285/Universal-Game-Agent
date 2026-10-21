import json
import threading

import pytest

from uga.supervisor.long_run import LongRunManager
from uga.supervisor.soak import run_soak


def test_soak_records_real_milestones_and_refuses_stale_directory(tmp_path):
    result = run_soak(0.1, tmp_path / "soak", milestones=(0.05, 0.1))
    assert result["passed"] and result["elapsed_s"] >= 0.1
    assert result["completed_milestones_s"] == [0.05, 0.1]
    milestone = json.loads((tmp_path / "soak" / "milestone-0.1s.json").read_text())
    assert milestone["run_id"] == result["run_id"] and milestone["passed"]
    with pytest.raises(FileExistsError):
        run_soak(0.1, tmp_path / "soak")


def test_soak_timer_starts_after_source_inventory(tmp_path, monkeypatch):
    import time

    def delayed_fingerprint():
        time.sleep(0.15)
        return "fixture-source-fingerprint"

    monkeypatch.setattr("uga.supervisor.soak.source_fingerprint", delayed_fingerprint)
    result = run_soak(0.05, tmp_path / "delayed", milestones=(0.05,))
    assert result["passed"] and result["episodes"] > 0
    assert result["elapsed_s"] >= 0.05


def test_cancelled_soak_and_memory_budget_cannot_pass(tmp_path):
    cancel = threading.Event()
    cancel.set()
    cancelled = run_soak(10, tmp_path / "cancelled", cancel=cancel)
    assert cancelled["cancelled"] and not cancelled["passed"]
    over_budget = run_soak(10, tmp_path / "limited", rss_limit_mb=1)
    assert not over_budget["passed"] and over_budget["error"] == "memory budget exceeded"


def test_background_soak_reuses_owned_process_and_cancels_cleanly(tmp_path):
    manager = LongRunManager(tmp_path / "long-run")
    try:
        first = manager.start(60)
        assert first["running"]
        assert manager.start(60)["pid"] == first["pid"]
    finally:
        stopped = manager.stop()
    assert not stopped["running"]
    assert stopped["status"] == "cancelled"
    assert stopped["summary"]["cancelled"] and not stopped["summary"]["passed"]
    assert manager.stop()["status"] == "cancelled"
