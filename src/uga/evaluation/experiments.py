from uuid import uuid4

from uga.core.contracts import ArtifactReference, EvaluationResult
from uga.core.errors import AuthorizationRequired, UGAError
from uga.memory.store import Store

POLICY_KEYS = ("attack_range", "navigation_mode")


def with_active_policy(store: Store, parameters: dict) -> dict:
    """Fill each policy parameter the caller left unspecified from the approved active policy."""
    active = store.load_checkpoint("active-policy") or {}
    return {**{key: active[key] for key in POLICY_KEYS if key in active}, **parameters}


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
    for report in (baseline, candidate):
        if any(not 0 <= report.metrics[k] <= 1 for k in ("success_rate", "perception_accuracy")):
            raise ValueError("rates must be between zero and one")
        if report.metrics["mean_steps"] < 0 or report.metrics["end_to_end_p95_ms"] <= 0:
            raise ValueError("invalid step or latency measurement")
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
            "evidence": {
                "baseline": self.store.put_artifact(
                    baseline.model_dump_json().encode(), "application/json", "json"
                ).model_dump(mode="json"),
                "candidate": self.store.put_artifact(
                    candidate.model_dump_json().encode(), "application/json", "json"
                ).model_dump(mode="json"),
            },
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
        for key, report in (("baseline", baseline), ("candidate", candidate)):
            if "evidence" not in experiment:
                raise UGAError(
                    "legacy proposal lacks immutable evidence; propose the reports again"
                )
            reference = ArtifactReference.model_validate(experiment["evidence"][key])
            retained = EvaluationResult.model_validate_json(self.store.read_artifact(reference))
            if retained != report:
                raise UGAError("proposal differs from its immutable benchmark evidence")
        if not compare(baseline, candidate)["eligible"]:
            raise ValueError("candidate did not pass comparison")
        if experiment["status"] != "proposed":
            raise ValueError("experiment is not awaiting approval")
        experiment["status"] = "approved"

        def transition(read):
            pending = read("experiment:" + experiment_id)
            if (
                not pending
                or pending["status"] != "proposed"
                or pending["candidate"] != experiment["candidate"]
            ):
                raise ValueError("proposal changed or was already handled")
            return {
                "previous-policy": read("active-policy") or baseline.configuration["treatment"],
                "active-policy": candidate.configuration["treatment"],
                "experiment:" + experiment_id: experiment,
                "active-experiment": {"id": experiment_id},
            }

        self.store.atomic_checkpoints(transition)
        return experiment

    def rollback(self):
        previous = self.store.load_checkpoint("previous-policy")
        if previous is None:
            raise ValueError("no previous policy to restore")

        def transition(read):
            previous = read("previous-policy")
            if previous is None:
                raise ValueError("no previous policy to restore")
            updates = {"active-policy": previous}
            active = read("active-experiment")
            if active:
                experiment = read("experiment:" + active["id"])
                experiment["status"] = "rolled_back"
                updates["experiment:" + active["id"]] = experiment
            return updates

        self.store.atomic_checkpoints(transition)
        return previous

    def monitor(self, observed: EvaluationResult):
        active = self.store.load_checkpoint("active-experiment")
        if not active:
            raise ValueError("no promoted experiment")
        experiment = self.store.load_checkpoint("experiment:" + active["id"])
        if experiment["status"] != "approved":
            raise ValueError("no active approved candidate to monitor")
        if observed.configuration.get("treatment") != experiment["candidate"]["configuration"].get(
            "treatment"
        ):
            raise ValueError("observed treatment differs from the promoted candidate")
        baseline = EvaluationResult.model_validate(experiment["baseline"])
        comparison = compare(baseline, observed)
        if not comparison["eligible"]:
            self.rollback()
            return {"rolled_back": True, "comparison": comparison}
        return {"rolled_back": False, "comparison": comparison}
