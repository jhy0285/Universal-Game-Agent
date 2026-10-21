"""Actual Linux Godot window → MSS pixels → policy → opt-in test-game actions."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from uga.agents.builder.agent import generate, parse_requirements
from uga.agents.builder.godot import GodotAdapter
from uga.agents.player.perception import MSSCapture
from uga.integrations.process import terminate_owned
from uga.memory.store import atomic_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-external-tools", action="store_true")
    parser.add_argument("--xvfb", type=Path, required=True)
    parser.add_argument("--display", type=int, default=96)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_external_tools:
        raise ValueError("Godot and Xvfb execution need --allow-external-tools")
    if not 90 <= args.display <= 200:
        raise ValueError("Choose a dedicated display in [90,200]")
    if args.output.exists() or Path(f"/tmp/.X11-unix/X{args.display}").exists():
        raise FileExistsError("Use a new output directory and an unused display")
    args.output.mkdir(parents=True)
    environment = {
        "DISPLAY": f":{args.display}",
        "LIBGL_ALWAYS_SOFTWARE": "1",
        "LD_LIBRARY_PATH": str(args.xvfb.resolve().parent.parent / "lib/x86_64-linux-gnu"),
    }
    original = {key: os.environ.get(key) for key in environment}
    os.environ.update(environment)
    server = capture = None
    results = {
        "backend": "godot-mss-pixels",
        "input_backend": "authorized test-game file bridge",
        "runs": [],
    }
    try:
        with (args.output / "xvfb.log").open("w") as log:
            server = subprocess.Popen(
                [
                    str(args.xvfb.resolve()),
                    f":{args.display}",
                    "-screen",
                    "0",
                    "800x600x24",
                    "-nolisten",
                    "tcp",
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        deadline = time.monotonic() + 10
        while not Path(f"/tmp/.X11-unix/X{args.display}").exists():
            if server.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("Owned Xvfb did not become ready")
            time.sleep(0.02)
        project = args.output / "project"
        generate(parse_requirements("3 enemies"), project)
        adapter = GodotAdapter()
        results["import"] = adapter.validate(project, approved=True)
        capture = MSSCapture({"left": 0, "top": 0, "width": 640, "height": 448})
        for seed in (7, 11, 19, 23, 31):
            result = adapter.play(
                project, args.output / "play", approved=True, seed=seed, capture=capture
            )
            results["runs"].append(result)
            atomic_json(args.output / "results.json", results)
            assert result["success"] and result["perception_accuracy"] == 1, result
        results["passed"] = True
        atomic_json(args.output / "results.json", results)
        print(
            json.dumps(
                {"passed": True, "seeds": len(results["runs"]), "backend": results["backend"]}
            )
        )
    except BaseException as exc:
        results.update(passed=False, error=f"{type(exc).__name__}: {exc}")
        atomic_json(args.output / "results.json", results)
        raise
    finally:
        if capture:
            capture.close()
        if server:
            terminate_owned(server)
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    main()
