"""Explicit, reproducible engine checks against original UGA projects only."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

from uga.agents.builder.agent import generate, parse_requirements
from uga.agents.builder.godot import GodotAdapter
from uga.core.contracts import utcnow
from uga.core.errors import AuthorizationRequired
from uga.memory.store import atomic_json
from uga.workflows import build_play, reverse_build_play


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-external-tools", action="store_true")
    parser.add_argument("--export", action="store_true", help="Requires matching release templates")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_external_tools:
        raise AuthorizationRequired("Godot execution needs --allow-external-tools")
    if args.output.exists():
        raise FileExistsError("Use a new validation output directory")
    args.output.mkdir(parents=True)
    adapter = GodotAdapter()
    project = args.output / "project"
    generate(parse_requirements("2D arena with 3 enemies"), project)
    result = {
        "started_at": utcnow().isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "engine_sha256": hashlib.sha256(adapter.executable.read_bytes()).hexdigest(),
        "backend": "godot-ground-truth-bridge",
        "screenshot_perception_tested": False,
    }

    def record(name, value):
        result[name] = value
        atomic_json(args.output / "results.json", result)

    record("import", adapter.validate(project, approved=True))
    record("smoke", adapter.smoke(project, args.output / "smoke", approved=True))
    plays = []
    for seed in (7, 11, 19, 23, 31):
        plays.append(adapter.play(project, args.output / "play", approved=True, seed=seed))
        record("fixed_seed_play", plays)
    workflow = build_play("enemies 2", args.output / "workflow", backend="godot", approved=True)
    record("build_reverse_play", workflow)
    rebuilt = reverse_build_play(
        Path(workflow["generated"]["project"]),
        args.output / "rebuild",
        backend="godot",
        approved=True,
        authorized=True,
    )
    record("reverse_build_play", rebuilt)
    exports = {}
    if args.export:
        for preset, filename in (("Linux", "uga.x86_64"), ("Windows Desktop", "uga.exe")):
            target = args.output / "export" / filename
            exported = adapter.export(project, preset, target, approved=True)
            with target.open("rb") as stream:
                exported["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
            exported["size_bytes"] = target.stat().st_size
            exported["runtime_tested"] = False
            if (preset == "Linux" and platform.system() == "Linux") or (
                preset == "Windows Desktop" and platform.system() == "Windows"
            ):
                exported["play"] = adapter.play(
                    project, args.output / "export-play", approved=True, game_executable=target
                )
                exported["runtime_tested"] = True
            exports[preset] = exported
            record("exports", exports)
    record("finished_at", utcnow().isoformat())
    record("passed", True)
    print(
        json.dumps(
            {"passed": True, "seeds": len(plays), "report": str(args.output / "results.json")}
        )
    )


if __name__ == "__main__":
    main()
