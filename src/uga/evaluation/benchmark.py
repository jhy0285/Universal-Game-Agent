import hashlib
import json
import platform
import statistics
from pathlib import Path

from uga.agents.player.policies import RuleBasedPolicy
from uga.agents.player.runner import run_episode
from uga.core.contracts import EvaluationResult
from uga.evaluation.metrics import Metrics
from uga.memory.store import Store
from uga.test_game import ArenaConfig

DEFAULT_SEEDS = (7, 11, 19, 23, 31)


def run_benchmark(output: Path, seeds=DEFAULT_SEEDS, attack_range: float = 14) -> EvaluationResult:
    if not seeds:
        raise ValueError("benchmark must have at least one episode")
    output.mkdir(parents=True, exist_ok=True)
    timing = {}
    results = []
    for seed in seeds:
        result = run_episode(
            ArenaConfig(seed=seed),
            RuleBasedPolicy(attack_range),
            output / f"seed-{seed}",
            timing_sink=timing,
        )
        results.append(result)
    metrics = Metrics()
    metrics.samples.update(timing)
    values = metrics.summarize()
    values.update(
        cpu_seconds=sum(r.metrics["cpu_seconds"] for r in results),
        rss_mb=max(r.metrics["rss_mb"] for r in results),
        success_rate=sum(r.success for r in results) / len(results),
        perception_accuracy=statistics.mean(r.perception_accuracy for r in results),
        mean_steps=statistics.mean(r.steps for r in results),
    )
    conditions = {
        "backend": "reference-pixels-v1",
        "seeds": list(seeds),
        "enemy_count": 3,
        "speed": 4,
        "obstacles": True,
        "max_steps": 600,
    }
    report = EvaluationResult(
        benchmark="uga-arena-v1",
        seed=seeds[0],
        samples=len(results),
        configuration={
            "conditions": conditions,
            "conditions_sha256": hashlib.sha256(
                json.dumps(conditions, sort_keys=True).encode()
            ).hexdigest(),
            "environment": {"python": platform.python_version(), "platform": platform.platform()},
            "treatment": {"policy": "rule", "attack_range": attack_range},
        },
        metrics=values,
        passed=all(r.success and r.perception_accuracy == 1 for r in results),
    )
    store = Store(output / "store")
    artifact = store.put_artifact(
        report.model_dump_json(indent=2).encode(), "application/json", "json"
    )
    report.artifacts = [artifact]
    (output / "report.json").write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return report
