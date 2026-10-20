from uuid import uuid4

from uga.core.contracts import EvaluationResult
from uga.core.errors import AuthorizationRequired
from uga.memory.store import Store


def compare(
    baseline: EvaluationResult, candidate: EvaluationResult, latency_regression: float = 0.25
) -> dict:
    if baseline.benchmark != candidate.benchmark or baseline.samples != candidate.samples:
        raise ValueError("benchmark target/sample count differs")
    for key in ("conditions", "conditions_sha256", "environment"):
        if key not in baseline.configuration or baseline.configuration[
            key
        ] != candidate.configuration.get(key):
            raise ValueError(f"incomparable benchmark {key}")
    for metric in ("success_rate", "perception_accuracy", "mean_steps", "end_to_end_p95_ms"):
        if metric not in baseline.metrics or metric not in candidate.metrics:
            raise ValueError(f"missing comparison metric {metric}")
    delta = {
        k: candidate.metrics[k] - v for k, v in baseline.metrics.items() if k in candidate.metrics
    }
    reasons = []
    if not candidate.passed:
        reasons.append("candidate benchmark failed")
    for key in ("success_rate", "perception_accuracy"):
        if candidate.metrics[key] < baseline.metrics[key]:
            reasons.append(f"regressed {key}")
    if candidate.metrics["mean_steps"] > baseline.metrics["mean_steps"]:
        reasons.append("regressed mean_steps")
    if candidate.metrics["end_to_end_p95_ms"] > baseline.metrics["end_to_end_p95_ms"] * (
        1 + latency_regression
    ):
        reasons.append("regressed p95 latency")
    improved = (
        any(
            candidate.metrics[k] > baseline.metrics[k]
            for k in ("success_rate", "perception_accuracy")
        )
        or candidate.metrics["mean_steps"] < baseline.metrics["mean_steps"]
    )
    if not improved:
        reasons.append("no measured improvement")
    return {
        "eligible": not reasons,
        "reasons": reasons,
        "delta": delta,
        "latency_tolerance": latency_regression,
    }


class ExperimentManager:
    def __init__(self, store: Store):
        self.store = store

    def propose(self, baseline: EvaluationResult, candidate: EvaluationResult):
        comparison = compare(baseline, candidate)
        experiment = {
            "id": str(uuid4()),
            "baseline": baseline.model_dump(mode="json"),
            "candidate": candidate.model_dump(mode="json"),
            "comparison": comparison,
            "status": "proposed",
        }
        self.store.checkpoint("experiment:" + experiment["id"], experiment)
        return experiment

    def promote(self, experiment_id: str, *, approved: bool = False):
        if not approved:
            raise AuthorizationRequired("Explicit approval is required to promote a candidate")
        experiment = self.store.load_checkpoint("experiment:" + experiment_id)
        if not experiment:
            raise KeyError(experiment_id)
        baseline = EvaluationResult.model_validate(experiment["baseline"])
        candidate = EvaluationResult.model_validate(experiment["candidate"])
        if not compare(baseline, candidate)["eligible"]:
            raise ValueError("candidate did not pass comparison")
        if experiment["status"] != "proposed":
            raise ValueError("experiment is not awaiting approval")
        current = self.store.load_checkpoint("active-policy")
        self.store.checkpoint("previous-policy", current or baseline.configuration["treatment"])
        self.store.checkpoint("active-policy", candidate.configuration["treatment"])
        experiment["status"] = "approved"
        self.store.checkpoint("experiment:" + experiment_id, experiment)
        self.store.checkpoint("active-experiment", {"id": experiment_id})
        return experiment

    def rollback(self):
        previous = self.store.load_checkpoint("previous-policy")
        if previous is None:
            raise ValueError("no previous policy to restore")
        self.store.checkpoint("active-policy", previous)
        active = self.store.load_checkpoint("active-experiment")
        if active:
            experiment = self.store.load_checkpoint("experiment:" + active["id"])
            experiment["status"] = "rolled_back"
            self.store.checkpoint("experiment:" + active["id"], experiment)
        return previous

    def monitor(self, observed: EvaluationResult):
        active = self.store.load_checkpoint("active-experiment")
        if not active:
            raise ValueError("no promoted experiment")
        experiment = self.store.load_checkpoint("experiment:" + active["id"])
        baseline = EvaluationResult.model_validate(experiment["baseline"])
        comparison = compare(baseline, observed)
        if not comparison["eligible"]:
            self.rollback()
            return {"rolled_back": True, "comparison": comparison}
        return {"rolled_back": False, "comparison": comparison}
