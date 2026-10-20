import json
import time
from pathlib import Path

from uga.agents.player.perception import Frame, PixelPerception
from uga.agents.player.policies import RuleBasedPolicy, safe_state
from uga.agents.player.verification import verify_effect
from uga.core.contracts import Action, ActionDecision, Contract, utcnow
from uga.evaluation.metrics import Metrics
from uga.memory.store import atomic_json
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
    resume: dict | None = None,
    preview_path: Path | None = None,
) -> EpisodeResult:
    game = ReferenceArena.restore(resume) if resume else ReferenceArena(config)
    if resume and game.done:
        raise ValueError("checkpoint is already terminal; no new episode can be validated")
    if resume and config is not None and game.config != config:
        raise ValueError("resume configuration differs from requested configuration")
    config = game.config
    perception = PixelPerception()
    policy = policy or RuleBasedPolicy(config.attack_range)
    metrics = Metrics()
    correct = total = effects = 0
    reason = "step_limit"
    trace = None
    previous_state = previous_action = None
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
            if previous_state is not None:
                effects += verify_effect(previous_state, state, previous_action) is True
                previous_state = None
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
            action = ActionDecision.model_validate(policy.decide(state))
            metrics.observe("decision", (time.perf_counter() - start) * 1000)
            if (
                action.based_on_frame != state.frame_id
                or (utcnow() - state.captured_at).total_seconds() > 0.5
            ):
                reason = "stale_decision"
                break
            if action.confidence < 0.6:
                action = action.model_copy(update={"action": Action.WAIT})
            start = time.perf_counter()
            # Reference control is a bounded single simulation step; desktop control uses GuardedController.
            game.step(action.action)
            previous_state, previous_action = state, action.action
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
            if game.tick % 10 == 0:
                if output:
                    atomic_json(output / "checkpoint.json", game.checkpoint())
                    atomic_json(
                        output / "current.json",
                        {
                            "state": state.model_dump(mode="json"),
                            "decision": action.model_dump(mode="json"),
                        },
                    )
                if preview_path:
                    preview_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = preview_path.with_suffix(".tmp")
                    game.render().save(temporary, format="PNG")
                    temporary.replace(preview_path)
        if game.won:
            reason = "goal_complete"
        elif game.hp <= 0:
            reason = "player_dead"
        if previous_state is not None:
            final_state = perception.analyze(Frame(game.render(), game.tick, utcnow()))
            effects += verify_effect(previous_state, final_state, previous_action) is True
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
