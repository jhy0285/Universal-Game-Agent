import json
import time
from pathlib import Path

from uga.agents.player.perception import Frame, PixelPerception
from uga.agents.player.policies import RuleBasedPolicy, safe_state
from uga.core.contracts import Contract, utcnow
from uga.evaluation.metrics import Metrics
from uga.test_game import ArenaConfig, ReferenceArena


class EpisodeResult(Contract):
    seed: int
    success: bool
    steps: int
    perception_accuracy: float
    verified_effects: int
    stop_reason: str
    metrics: dict[str, float]


def run_episode(
    config: ArenaConfig | None = None,
    policy=None,
    output: Path | None = None,
    cancel=None,
    heartbeat=None,
    timing_sink=None,
) -> EpisodeResult:
    game = ReferenceArena(config)
    config = game.config
    perception = PixelPerception()
    policy = policy or RuleBasedPolicy(config.attack_range)
    metrics = Metrics()
    correct = total = effects = 0
    reason = "step_limit"
    trace = None
    if output:
        output.mkdir(parents=True, exist_ok=True)
        trace = (output / "trace.jsonl").open("w", encoding="utf-8")
    try:
        while not game.done:
            if cancel and cancel.is_set():
                reason = "cancelled"
                break
            begin = time.perf_counter()
            frame = Frame(game.render(), game.tick, utcnow())
            metrics.observe("capture", (time.perf_counter() - begin) * 1000)
            start = time.perf_counter()
            state = perception.analyze(frame)
            metrics.observe("perception", (time.perf_counter() - start) * 1000)
            truth = game.truth()
            checks = [
                state.hp is not None and state.hp.value == truth["hp"],
                len(state.enemies) == truth["enemies"],
                state.player_position is not None
                and [state.player_position.value.x, state.player_position.value.y]
                == truth["player"],
            ]
            correct += sum(checks)
            total += len(checks)
            if not safe_state(state):
                reason = "safety_stop"
                break
            start = time.perf_counter()
            action = policy.decide(state)
            metrics.observe("decision", (time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            # Reference control is a bounded single simulation step; desktop control uses GuardedController.
            effects += bool(game.step(action.action))
            metrics.observe("control", (time.perf_counter() - start) * 1000)
            metrics.observe("end_to_end", (time.perf_counter() - begin) * 1000)
            if trace:
                trace.write(
                    json.dumps(
                        {
                            "state": state.model_dump(mode="json"),
                            "decision": action.model_dump(mode="json"),
                            "truth": truth,
                            "effect": game.last_effect,
                        }
                    )
                    + "\n"
                )
            if heartbeat:
                heartbeat(game.tick)
        if game.won:
            reason = "goal_complete"
        elif game.hp <= 0:
            reason = "player_dead"
        result = EpisodeResult(
            seed=config.seed,
            success=game.won,
            steps=game.tick,
            perception_accuracy=correct / total if total else 0,
            verified_effects=effects,
            stop_reason=reason,
            metrics=metrics.summarize(),
        )
        if timing_sink is not None:
            for name, values in metrics.samples.items():
                timing_sink.setdefault(name, []).extend(values)
        if output:
            (output / "result.json").write_text(
                result.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
            game.render().save(output / "last-frame.png")
        return result
    finally:
        if trace:
            trace.close()
