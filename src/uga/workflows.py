from pathlib import Path

from uga.agents.builder.agent import generate, parse_requirements
from uga.agents.player.runner import run_episode
from uga.agents.reverse.agent import analyze
from uga.core.errors import CapabilityUnavailable
from uga.memory.store import atomic_json
from uga.test_game import ArenaConfig


def build_play(requirements: str, output: Path, heartbeat=None) -> dict:
    spec = parse_requirements(requirements)
    generated = generate(spec, output / "project")
    analyzed = analyze(output / "project", output / "analysis", authorized=True)
    result = run_episode(
        ArenaConfig(enemy_count=spec.combat["enemies"]),
        output=output / "reference-play",
        heartbeat=heartbeat,
    )
    report = {
        "generated": generated,
        "analysis": analyzed.model_dump(mode="json"),
        "reference_player": result.model_dump(mode="json"),
        "godot_executed": False,
        "verified_backend": "CPU reference only; use godot-check/play for engine validation",
    }
    atomic_json(output / "workflow.json", report)
    return report


def reverse_build_play(source: Path, output: Path, *, authorized=False, heartbeat=None):
    spec = analyze(source, output / "source-analysis", authorized=authorized)
    if spec.genre != "top_down_arena":
        raise CapabilityUnavailable(
            "No supported, source-declared arena GameSpec was recovered; reconstruction cannot be inferred from unknown binary mechanics"
        )
    generated = generate(spec, output / "project")
    result = run_episode(
        ArenaConfig(enemy_count=spec.combat.get("enemies", 3)),
        output=output / "reference-play",
        heartbeat=heartbeat,
    )
    report = {
        "analysis": spec.model_dump(mode="json"),
        "generated": generated,
        "reference_player": result.model_dump(mode="json"),
        "godot_executed": False,
    }
    atomic_json(output / "workflow.json", report)
    return report
