from pathlib import Path

from uga.agents.builder.godot import GodotAdapter
from uga.core.errors import AuthorizationRequired
from uga.memory.store import atomic_json


def validate_project(
    project: Path,
    output: Path,
    *,
    approved=False,
    export_preset: str | None = None,
    heartbeat=None,
) -> dict:
    """Import, test and play an owned Godot project; export only when requested."""
    if not approved:
        raise AuthorizationRequired("Godot project execution needs explicit approval")
    if export_preset not in (None, "Linux", "Windows Desktop"):
        raise ValueError("unsupported export preset")
    output.mkdir(parents=True, exist_ok=True)
    adapter = GodotAdapter()
    stages = {}

    def record(name, result):
        stages[name] = result
        atomic_json(output / "build-report.json", stages)

    record("import", adapter.validate(project, approved=True, heartbeat=heartbeat))
    record("smoke", adapter.smoke(project, output / "smoke", approved=True, heartbeat=heartbeat))
    record("player", adapter.play(project, output / "play", approved=True, heartbeat=heartbeat))
    if export_preset:
        filename = "uga.exe" if export_preset == "Windows Desktop" else "uga.x86_64"
        record(
            "export",
            adapter.export(
                project,
                export_preset,
                output / "export" / filename,
                approved=True,
                heartbeat=heartbeat,
            ),
        )
    return stages
