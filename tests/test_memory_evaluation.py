import pytest

from uga.core.contracts import EvaluationResult, TaskSpec, TaskStatus
from uga.core.errors import AuthorizationRequired, UGAError
from uga.evaluation.benchmark import run_benchmark
from uga.evaluation.experiments import ExperimentManager, compare
from uga.memory.store import Store
from uga.supervisor.soak import run_soak


def test_artifact_integrity_and_sqlite_roundtrip(tmp_path):
    store = Store(tmp_path)
    task = TaskSpec(agent="player", operation="play")
    store.create_task(task)
    store.update_task(task.task_id, TaskStatus.SUCCEEDED, {"success": True})
    assert store.task(task.task_id)["result"]["success"]
    ref = store.put_artifact(b"hello")
    assert store.read_artifact(ref) == b"hello"
    (tmp_path / ref.path).write_bytes(b"corrupted")
    with pytest.raises(UGAError):
        store.read_artifact(ref)
    with pytest.raises(UGAError):
        store.put_artifact(b"hello")
    with pytest.raises(ValueError):
        store.put_artifact(b"x", suffix="../x")
    store.checkpoint("watchdog", {"tick": 42})
    assert Store(tmp_path).load_checkpoint("watchdog") == {"tick": 42}


def reports():
    config = {
        "conditions": {"seeds": [7]},
        "conditions_sha256": "fixed",
        "environment": {"python": "3.11"},
        "treatment": {"attack_range": 8},
    }
    baseline = EvaluationResult(
        benchmark="arena",
        seed=7,
        samples=1,
        passed=True,
        configuration=config,
        metrics={
            "success_rate": 1,
            "perception_accuracy": 1,
            "mean_steps": 100,
            "end_to_end_p95_ms": 10,
        },
    )
    candidate = baseline.model_copy(deep=True)
    candidate.configuration["treatment"] = {"attack_range": 14}
    candidate.metrics["mean_steps"] = 80
    return baseline, candidate


def test_comparison_approval_and_automatic_rollback(tmp_path):
    baseline, candidate = reports()
    manager = ExperimentManager(Store(tmp_path))
    experiment = manager.propose(baseline, candidate)
    assert experiment["comparison"]["eligible"]
    with pytest.raises(AuthorizationRequired):
        manager.promote(experiment["id"])
    manager.promote(experiment["id"], approved=True)
    assert manager.store.load_checkpoint("active-policy")["attack_range"] == 14
    bad = candidate.model_copy(deep=True)
    bad.metrics["success_rate"] = 0.5
    assert manager.monitor(bad)["rolled_back"]
    assert manager.store.load_checkpoint("active-policy")["attack_range"] == 8


def test_incomparable_conditions_and_regression_rejected(tmp_path):
    baseline, candidate = reports()
    candidate.configuration["conditions"] = {"seeds": [19]}
    with pytest.raises(ValueError, match="conditions"):
        compare(baseline, candidate)
    baseline, candidate = reports()
    candidate.metrics["end_to_end_p95_ms"] = 30
    manager = ExperimentManager(Store(tmp_path))
    experiment = manager.propose(baseline, candidate)
    with pytest.raises(ValueError):
        manager.promote(experiment["id"], approved=True)


@pytest.mark.performance
def test_real_benchmark_and_soak_execute_episodes(tmp_path):
    report = run_benchmark(tmp_path / "bench", seeds=(7, 11))
    assert report.samples == 2 and report.passed
    assert report.metrics["success_rate"] == 1
    summary = run_soak(0.1, tmp_path / "soak")
    assert summary["episodes"] > 0 and summary["elapsed_s"] >= 0.1 and summary["passed"]
