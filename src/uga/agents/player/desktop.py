import json
import time
from pathlib import Path

from uga.agents.player.verification import verify_effect
from uga.core.errors import SafetyStop
from uga.evaluation.metrics import Metrics
from uga.memory.store import atomic_json


def run_desktop(
    capture, perception, policy, controller, output: Path, *, max_seconds=60, cancel=None
):
    """Only captures and controls an already-running, explicitly authorized foreground game."""
    if not 0 < max_seconds <= 57600:
        raise ValueError("desktop runtime must be in (0,16 hours]")
    output.mkdir(parents=True, exist_ok=True)
    metrics = Metrics()
    start = time.monotonic()
    frames = effects = 0
    previous = previous_action = None
    reason = "runtime_limit"
    success = False
    try:
        with (output / "trace.jsonl").open("w", encoding="utf-8") as trace:
            while time.monotonic() - start < max_seconds:
                if cancel and cancel.is_set():
                    reason = "cancelled"
                    break
                began = time.perf_counter()
                frame = capture.capture()
                metrics.observe("capture", (time.perf_counter() - began) * 1000)
                at = time.perf_counter()
                state = perception.analyze(frame)
                frames += 1
                metrics.observe("perception", (time.perf_counter() - at) * 1000)
                if previous is not None:
                    effects += verify_effect(previous, state, previous_action) is True
                if state.auth_required and state.auth_required.value:
                    reason = "human_handoff"
                    atomic_json(
                        output / "human-handoff.json",
                        {
                            "reason": "authentication requested",
                            "frame": state.frame_id,
                            "input_stopped": True,
                        },
                    )
                    break
                if state.goal_complete and state.goal_complete.value:
                    success = True
                    reason = "goal_complete"
                    break
                at = time.perf_counter()
                action = policy.decide(state)
                metrics.observe("decision", (time.perf_counter() - at) * 1000)
                at = time.perf_counter()
                controller.perform(action, state)
                metrics.observe("control", (time.perf_counter() - at) * 1000)
                metrics.observe("end_to_end", (time.perf_counter() - began) * 1000)
                previous, previous_action = state, action.action
                trace.write(
                    json.dumps(
                        {
                            "state": state.model_dump(mode="json"),
                            "decision": action.model_dump(mode="json"),
                        }
                    )
                    + "\n"
                )
                if frames % 10 == 0:
                    temporary = output / "last-frame.tmp"
                    frame.image.save(temporary, format="PNG")
                    temporary.replace(output / "last-frame.png")
                time.sleep(max(0, 0.1 - (time.perf_counter() - began)))
    except KeyboardInterrupt:
        reason = "cancelled"
    except SafetyStop as exc:
        reason = "safety_stop: " + str(exc)
    finally:
        try:
            controller.emergency_stop()
        finally:
            capture.close()
    result = {
        "backend": "windows-desktop",
        "success": success,
        "frames": frames,
        "verified_effects": effects,
        "stop_reason": reason,
        "metrics": metrics.summarize(),
    }
    atomic_json(output / "result.json", result)
    return result
