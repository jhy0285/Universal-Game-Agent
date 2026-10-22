from pathlib import Path

from uga.agents.builder.agent import generate, parse_requirements
from uga.agents.player.policies import RuleBasedPolicy
from uga.agents.player.runner import run_episode
from uga.agents.reverse.agent import analyze
from uga.core.errors import AuthorizationRequired, CapabilityUnavailable
from uga.memory.store import atomic_json
from uga.test_game import ArenaConfig


def _check_backend(backend, approved, export_preset):
    if backend not in ("reference", "godot"):
        raise ValueError("unsupported player backend")
    if backend == "godot" and not approved:
        raise AuthorizationRequired("Godot workflow execution needs explicit approval")
    if export_preset and backend != "godot":
        raise ValueError("export requires the godot backend")


def _play(spec, output, backend, approved, export_preset, heartbeat):
    if backend == "godot":
        from uga.agents.builder.pipeline import validate_project

        stages = validate_project(
            output / "project",
            output / "engine",
            approved=approved,
            export_preset=export_preset,
            heartbeat=heartbeat,
        )
        return {
            "engine": stages,
            "godot_executed": True,
            "verified_backend": stages["player"]["backend"],
        }
    config = ArenaConfig(
        enemy_count=spec.combat.get("enemies", 3),
        speed=spec.movement.get("speed", 4),
        attack_range=spec.combat.get("attack_range", 14),
    )
    result = run_episode(
        config,
        RuleBasedPolicy(config.attack_range),
        output=output / "reference-play",
        heartbeat=heartbeat,
    )
    return {
        "reference_player": result.model_dump(mode="json"),
        "godot_executed": False,
        "verified_backend": "reference-pixels-v1",
    }


def build_play(
    requirements: str,
    output: Path,
    heartbeat=None,
    *,
    backend="reference",
    approved=False,
    export_preset=None,
) -> dict:
    _check_backend(backend, approved, export_preset)
    spec = parse_requirements(requirements)
    generated = generate(spec, output / "project")
    analyzed = analyze(
        output / "project", output / "analysis", authorized=True, heartbeat=heartbeat
    )
    report = {
        "generated": generated,
        "analysis": analyzed.model_dump(mode="json"),
        **_play(spec, output, backend, approved, export_preset, heartbeat),
    }
    generated["built"] = "export" in report.get("engine", {})
    atomic_json(output / "workflow.json", report)
    return report


def reverse_build_play(
    source: Path,
    output: Path,
    *,
    authorized=False,
    heartbeat=None,
    backend="reference",
    approved=False,
    export_preset=None,
):
    _check_backend(backend, approved, export_preset)
    spec = analyze(source, output / "source-analysis", authorized=authorized, heartbeat=heartbeat)
    if spec.genre != "top_down_arena":
        raise CapabilityUnavailable(
            "No supported, source-declared arena GameSpec was recovered; reconstruction cannot be inferred from unknown binary mechanics"
        )
    generated = generate(spec, output / "project")
    report = {
        "analysis": spec.model_dump(mode="json"),
        "generated": generated,
        **_play(spec, output, backend, approved, export_preset, heartbeat),
    }
    generated["built"] = "export" in report.get("engine", {})
    atomic_json(output / "workflow.json", report)
    return report
