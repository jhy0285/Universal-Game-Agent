import json
import shutil
import time
from pathlib import Path
from uuid import uuid4

from uga.agents.player.perception import Frame, PixelPerception
from uga.agents.player.policies import RuleBasedPolicy, safe_state
from uga.agents.player.verification import verify_effect
from uga.core.contracts import Detection, GameState, Point, utcnow
from uga.core.errors import CapabilityUnavailable, SafetyStop, UGAError
from uga.evaluation.metrics import Metrics
from uga.integrations.process import run_tool
from uga.memory.store import atomic_json


def _truth_state(raw):
    def detected(value):
        return Detection(value=value, confidence=1, source="godot-test-ground-truth/v1")

    return GameState(
        frame_id=raw["tick"],
        captured_at=utcnow(),
        player_position=detected(Point(x=raw["player"][0], y=raw["player"][1])),
        hp=detected(float(raw["hp"])),
        enemies=[detected(Point(x=p[0], y=p[1])) for p in raw["enemies"]],
        items=[detected(Point(x=p[0], y=p[1])) for p in raw["items"]],
        obstacles=raw["obstacles"],
        ui_state="authentication" if raw["auth_required"] else "gameplay",
        auth_required=detected(raw["auth_required"]),
        goal_complete=detected(raw["won"]),
    )


class GodotAdapter:
    def __init__(self, executable: Path | None = None):
        found = str(executable) if executable else shutil.which("godot") or shutil.which("godot4")
        if not found:
            raise CapabilityUnavailable("Install Godot 4 from its official distribution")
        self.executable = Path(found).resolve()

    def validate(self, project: Path, *, approved=False, heartbeat=None):
        result = run_tool(
            [
                str(self.executable),
                "--headless",
                "--path",
                str(project.resolve()),
                "--editor",
                "--import",
                "--quit",
            ],
            project,
            approved=approved,
            driver=heartbeat,
            max_rss_mb=1024,
        )
        if any(
            marker in result.output for marker in ("ERROR:", "Parse Error", "Failed to load script")
        ):
            raise UGAError("Godot import/parse failed: " + result.output[-4000:])
        return {
            "imported": True,
            "elapsed_s": result.elapsed_s,
            "log": result.output,
            "engine_resources": result.resources,
        }

    def smoke(self, project: Path, output: Path, *, approved=False, heartbeat=None):
        output.mkdir(parents=True, exist_ok=True)
        run_id = str(uuid4())
        report = output.resolve() / f"smoke-{run_id}.json"
        command = [
            str(self.executable),
            "--headless",
            "--path",
            str(project.resolve()),
            "--script",
            "res://smoke_test.gd",
            "--",
            f"--uga-report={report}",
            f"--uga-run-id={run_id}",
        ]
        result = run_tool(command, project, approved=approved, driver=heartbeat)
        (output / "godot-smoke.log").write_text(result.output, encoding="utf-8")
        if not report.exists():
            raise UGAError("Godot did not produce this run's test result")
        data = json.loads(report.read_text(encoding="utf-8"))
        if (
            data.get("run_id") != run_id
            or data.get("checks", 0) < 6
            or data.get("passed") is not True
        ):
            raise UGAError("Godot smoke checks failed or result identity is stale")
        data["engine_resources"] = result.resources
        return data

    def play(
        self,
        project: Path,
        output: Path,
        *,
        approved=False,
        timeout_s=60,
        heartbeat=None,
        seed: int | None = None,
        game_executable: Path | None = None,
        capture=None,
    ):
        """Explicit engine truth control or MSS pixel perception with test-game input."""
        run_id = str(uuid4())
        bridge = output.resolve() / run_id
        bridge.mkdir(parents=True)
        report = bridge / "report.json"
        metrics = Metrics()
        configuration = project / "arena.json"
        config = (
            json.loads(configuration.read_text(encoding="utf-8")) if configuration.is_file() else {}
        )
        policy = RuleBasedPolicy(config.get("attack_range", 14))
        last_tick = -1
        sent_at = None
        frames = 0
        perception = PixelPerception() if capture else None
        correct = total = effects = 0
        previous_state = previous_action = None
        last_progress = time.monotonic()

        def drive():
            nonlocal last_tick, sent_at, frames, last_progress
            nonlocal correct, total, effects, previous_state, previous_action
            if heartbeat:
                heartbeat()
            if time.monotonic() - last_progress > 5:
                raise TimeoutError("Godot gameplay stopped acknowledging actions")
            path = bridge / "state.json"
            if not path.exists():
                return
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("run_id") != run_id:
                raise UGAError("bridge run identity mismatch")
            if raw["tick"] == last_tick:
                return
            last_progress = time.monotonic()
            if sent_at is not None:
                metrics.observe("engine_round_trip", (time.perf_counter() - sent_at) * 1000)
            last_tick = raw["tick"]
            frames += 1
            frame_begin = time.perf_counter()
            if capture:
                begin = time.perf_counter()
                captured = capture.capture()
                metrics.observe("capture", (time.perf_counter() - begin) * 1000)
                begin = time.perf_counter()
                state = perception.analyze(Frame(captured.image, raw["tick"], captured.captured_at))
                metrics.observe("perception", (time.perf_counter() - begin) * 1000)
                temporary = bridge / "last-frame.tmp"
                captured.image.save(temporary, format="PNG")
                temporary.replace(bridge / "last-frame.png")
                checks = [
                    state.hp is not None and state.hp.value == raw["hp"],
                    len(state.enemies) == len(raw["enemies"]),
                    state.player_position is not None
                    and state.player_position.value is not None
                    and [state.player_position.value.x, state.player_position.value.y]
                    == raw["player"],
                ]
                correct += sum(checks)
                total += len(checks)
                if previous_state is not None:
                    effects += verify_effect(previous_state, state, previous_action) is True
                if not safe_state(state):
                    raise SafetyStop("Rendered frame is unknown or requires human handoff")
                if raw["done"]:
                    atomic_json(
                        bridge / "action.json",
                        {"run_id": run_id, "frame": last_tick, "action": "finish"},
                    )
                    return
            else:
                state = _truth_state(raw)
            if raw["auth_required"]:
                raise SafetyStop("Godot requested human handoff")
            begin = time.perf_counter()
            action = policy.decide(state)
            metrics.observe("decision", (time.perf_counter() - begin) * 1000)
            previous_state, previous_action = state, action.action
            begin = time.perf_counter()
            atomic_json(
                bridge / "action.json",
                {"run_id": run_id, "frame": last_tick, "action": action.action.value},
            )
            metrics.observe("control", (time.perf_counter() - begin) * 1000)
            sent_at = time.perf_counter()
            if capture:
                metrics.observe("end_to_end", (sent_at - frame_begin) * 1000)
                with (bridge / "trace.jsonl").open("a", encoding="utf-8") as trace:
                    trace.write(
                        json.dumps(
                            {
                                "state": state.model_dump(mode="json"),
                                "decision": action.model_dump(mode="json"),
                            }
                        )
                        + "\n"
                    )

        command = [str(game_executable.resolve()) if game_executable else str(self.executable)]
        command.extend(
            ["--resolution", "640x448", "--position", "0,0", "--audio-driver", "Dummy"]
            if capture
            else ["--headless"]
        )
        if not game_executable:
            command.extend(["--path", str(project.resolve())])
        command.extend(
            [
                "--",
                f"--uga-bridge={bridge}",
                f"--uga-report={report}",
                f"--uga-run-id={run_id}",
            ]
        )
        if seed is not None:
            command.append(f"--uga-seed={int(seed)}")
        if capture:
            command.append("--uga-render-sync")
        result = run_tool(
            command,
            project,
            approved=approved,
            timeout_s=timeout_s,
            driver=drive,
        )
        (bridge / "godot.log").write_text(result.output, encoding="utf-8")
        if not report.exists():
            raise UGAError("no current Godot gameplay result")
        data = json.loads(report.read_text(encoding="utf-8"))
        if data.get("run_id") != run_id or data.get("won") is not True or frames < 2:
            raise UGAError("Godot gameplay did not reach the goal")
        outcome = {
            "backend": "godot-mss-pixels" if capture else "godot-ground-truth-bridge",
            "exported_game": game_executable is not None,
            "seed_override": seed,
            "success": True,
            "frames": frames,
            "truth": data,
            "metrics": metrics.summarize(),
            "engine_resources": result.resources,
        }
        if capture:
            outcome["perception_accuracy"] = correct / total if total else 0
            outcome["verified_effects"] = effects
        atomic_json(bridge / "evaluation.json", outcome)
        return outcome

    def export(self, project: Path, preset: str, output: Path, *, approved=False, heartbeat=None):
        if preset not in ("Windows Desktop", "Linux"):
            raise ValueError("unsupported export preset")
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError(output)
        result = run_tool(
            [
                str(self.executable),
                "--headless",
                "--path",
                str(project.resolve()),
                "--export-release",
                preset,
                str(output),
            ],
            project,
            approved=approved,
            timeout_s=180,
            driver=heartbeat,
            max_rss_mb=1024,
        )
        if "ERROR:" in result.output:
            raise UGAError("Godot export reported errors: " + result.output[-4000:])
        if not output.is_file() or output.stat().st_size == 0:
            raise UGAError("Godot produced no exported game")
        return {
            "exported": True,
            "path": str(output),
            "log": result.output,
            "engine_resources": result.resources,
        }
