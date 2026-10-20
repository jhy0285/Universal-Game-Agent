import argparse
import json
from pathlib import Path

from uga.capabilities import capabilities
from uga.core.contracts import CONTRACTS


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uga", description="Universal Game Agent")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "doctor", help="Report installed capabilities without running external tools"
    )
    schemas = commands.add_parser("schemas", help="Export versioned JSON Schema contracts")
    schemas.add_argument("--output", type=Path, default=Path("schemas"))
    serve = commands.add_parser("serve", help="Start the local API and dashboard")
    serve.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--state-dir", type=Path, default=Path(".uga"))
    serve.add_argument("--analysis-root", type=Path, default=Path.cwd())
    service = commands.add_parser(
        "service", help="Start, inspect or stop the owned local dashboard server"
    )
    service.add_argument("action", choices=["start", "status", "stop"])
    service.add_argument("--state-dir", type=Path, default=Path(".uga"))
    service.add_argument("--port", type=int, default=8765)
    player = commands.add_parser("player", help="Play the reference test arena from pixels")
    player.add_argument("--seed", type=int, default=7)
    player.add_argument("--max-steps", type=int, default=600)
    player.add_argument("--attack-range", type=float)
    player.add_argument("--navigation-mode", choices=["euclidean", "geodesic"])
    player.add_argument("--resume", type=Path)
    player.add_argument("--output", type=Path, default=Path(".uga/player"))
    desktop = commands.add_parser(
        "desktop-play", help="Capture/control an explicitly authorized Windows foreground test game"
    )
    desktop.add_argument("--target-pid", type=int, required=True)
    desktop.add_argument(
        "--region", type=int, nargs=4, metavar=("LEFT", "TOP", "WIDTH", "HEIGHT"), required=True
    )
    desktop.add_argument("--authorized", action="store_true")
    desktop.add_argument("--seconds", type=float, default=60)
    desktop.add_argument("--actions", type=Path, default=Path("configs/actions.json"))
    desktop.add_argument("--output", type=Path, default=Path(".uga/desktop"))
    benchmark = commands.add_parser("benchmark", help="Run the fixed-seed pixel benchmark")
    benchmark.add_argument("--attack-range", type=float, default=14)
    benchmark.add_argument(
        "--navigation-mode", choices=["euclidean", "geodesic"], default="euclidean"
    )
    benchmark.add_argument("--output", type=Path, default=Path(".uga/benchmark"))
    comparison = commands.add_parser("compare", help="Compare reports under identical conditions")
    comparison.add_argument("baseline", type=Path)
    comparison.add_argument("candidate", type=Path)
    soak = commands.add_parser("soak", help="Real wall-clock repeated-play health test")
    soak.add_argument("--seconds", type=float, default=1800)
    soak.add_argument("--output", type=Path, default=Path(".uga/soak"))
    long_run = commands.add_parser(
        "soak-service", help="Start, inspect or stop an owned background soak"
    )
    long_run.add_argument("action", choices=["start", "status", "stop"])
    long_run.add_argument("--seconds", type=float, default=57600)
    long_run.add_argument("--output", type=Path, required=True)
    builder = commands.add_parser("builder", help="Generate an original Godot arena project")
    builder.add_argument("--requirements", default="2D arena with 3 enemies")
    builder.add_argument("--output", type=Path, required=True)
    builder.add_argument("--validate", action="store_true", help="Import, test and play in Godot")
    builder.add_argument("--allow-external-tools", action="store_true")
    builder.add_argument("--export-preset", choices=["Linux", "Windows Desktop"])
    for name in ("builder-edit", "builder-repair"):
        revision = commands.add_parser(name, help="Revise a separate, authorized Godot candidate")
        revision.add_argument("source", type=Path)
        revision.add_argument("--output", type=Path, required=True)
        revision.add_argument("--authorized", action="store_true")
        revision.add_argument("--allow-external-tools", action="store_true")
        if name == "builder-edit":
            revision.add_argument("--patch", type=Path, required=True)
            revision.add_argument("--validate", action="store_true")
    reverse = commands.add_parser("reverse", help="Bounded static analysis; never execute samples")
    reverse.add_argument("path", type=Path)
    reverse.add_argument("--authorized", action="store_true")
    reverse.add_argument("--output", type=Path, default=Path(".uga/reverse"))
    reverse_tool = commands.add_parser(
        "reverse-tool", help="Explicit JADX/Ghidra analysis of a trusted authorized sample"
    )
    reverse_tool.add_argument("tool", choices=["jadx", "ghidra"])
    reverse_tool.add_argument("path", type=Path)
    reverse_tool.add_argument("--output", type=Path, required=True)
    reverse_tool.add_argument("--authorized", action="store_true")
    reverse_tool.add_argument("--trusted-input", action="store_true")
    reverse_tool.add_argument("--allow-external-tools", action="store_true")
    reverse_tool.add_argument("--executable", type=Path)
    reverse_tool.add_argument("--java", type=Path)
    reverse_tool.add_argument("--installation", type=Path)
    workflow = commands.add_parser("workflow", help="Generate → static analysis → reference Player")
    workflow.add_argument("--requirements", default="2D arena with 3 enemies")
    workflow.add_argument("--output", type=Path, required=True)
    rebuild = commands.add_parser(
        "rebuild", help="Source-declared GameSpec → Builder → reference Player"
    )
    rebuild.add_argument("source", type=Path)
    rebuild.add_argument("--authorized", action="store_true")
    rebuild.add_argument("--output", type=Path, required=True)
    for command in (workflow, rebuild):
        command.add_argument("--backend", choices=["reference", "godot"], default="reference")
        command.add_argument("--allow-external-tools", action="store_true")
        command.add_argument("--export-preset", choices=["Linux", "Windows Desktop"])
    improve = commands.add_parser(
        "improve", help="Measure a parameter candidate and save a proposal; never auto-approve"
    )
    improve.add_argument("--baseline-range", type=float, default=14)
    improve.add_argument("--candidate-range", type=float, default=14)
    improve.add_argument("--baseline-mode", choices=["euclidean", "geodesic"], default="euclidean")
    improve.add_argument("--candidate-mode", choices=["euclidean", "geodesic"], default="geodesic")
    improve.add_argument("--state-dir", type=Path, default=Path(".uga"))
    improve.add_argument("--output", type=Path, required=True)
    experiment = commands.add_parser(
        "experiment", help="Explicitly approve, monitor or roll back a measured candidate"
    )
    experiment.add_argument("action", choices=["list", "approve", "monitor", "rollback"])
    experiment.add_argument("--id")
    experiment.add_argument("--report", type=Path)
    experiment.add_argument("--approve", action="store_true")
    experiment.add_argument("--state-dir", type=Path, default=Path(".uga"))
    mcp = commands.add_parser("mcp", help="Run the local MCP stdio job adapter")
    mcp.add_argument("--state-dir", type=Path, default=Path(".uga/mcp"))
    mcp.add_argument("--analysis-root", type=Path, default=Path.cwd())
    for name in ("godot-check", "godot-play", "godot-export"):
        tool = commands.add_parser(name, help="Explicit external Godot operation")
        tool.add_argument("project", type=Path)
        tool.add_argument("--allow-external-tools", action="store_true")
        tool.add_argument("--output", type=Path, default=Path(".uga/godot"))
        if name == "godot-export":
            tool.add_argument("--preset", choices=["Linux", "Windows Desktop"], default="Linux")
        if name == "godot-play":
            tool.add_argument("--seed", type=int)
            tool.add_argument("--game-executable", type=Path)
    args = parser.parse_args(argv)
    if args.command == "doctor":
        print(json.dumps(capabilities(), indent=2, ensure_ascii=False))
    elif args.command == "schemas":
        args.output.mkdir(parents=True, exist_ok=True)
        for model in CONTRACTS:
            (args.output / f"{model.__name__}.schema.json").write_text(
                json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8"
            )
        print(f"Exported {len(CONTRACTS)} contracts to {args.output}")
    elif args.command == "service":
        from uga.supervisor.service import ServiceManager

        manager = ServiceManager(args.state_dir)
        result = (
            manager.start(args.port)
            if args.action == "start"
            else manager.status()
            if args.action == "status"
            else manager.stop()
        )
        print(json.dumps(result, indent=2))
        return 0 if args.action != "status" or result["healthy"] else 1
    elif args.command == "serve":
        import uvicorn

        from uga.api import create_app

        uvicorn.run(
            create_app(args.state_dir, analysis_root=args.analysis_root),
            host=args.host,
            port=args.port,
        )
    elif args.command == "player":
        from uga.agents.player.policies import RuleBasedPolicy
        from uga.agents.player.runner import run_episode
        from uga.memory.store import Store
        from uga.test_game import ArenaConfig

        active = Store(Path(".uga")).load_checkpoint("active-policy") or {}
        attack_range = (
            args.attack_range if args.attack_range is not None else active.get("attack_range", 14)
        )
        result = run_episode(
            None if args.resume else ArenaConfig(seed=args.seed, max_steps=args.max_steps),
            RuleBasedPolicy(
                attack_range, args.navigation_mode or active.get("navigation_mode", "euclidean")
            ),
            args.output,
            resume=json.loads(args.resume.read_text(encoding="utf-8")) if args.resume else None,
            preview_path=args.output / "last-frame.png",
        )
        print(result.model_dump_json(indent=2))
        return 0 if result.success else 1
    elif args.command == "benchmark":
        from uga.evaluation.benchmark import run_benchmark

        result = run_benchmark(
            args.output, attack_range=args.attack_range, navigation_mode=args.navigation_mode
        )
        print(result.model_dump_json(indent=2))
        return 0 if result.passed else 1
    elif args.command == "desktop-play":
        from uga.agents.player.controller import GuardedController, WindowsInputBackend
        from uga.agents.player.desktop import run_desktop
        from uga.agents.player.perception import MSSCapture, PixelPerception
        from uga.agents.player.policies import RuleBasedPolicy

        backend = WindowsInputBackend(args.target_pid, approved=args.authorized)
        capture = MSSCapture(
            dict(zip(("left", "top", "width", "height"), args.region, strict=True))
        )
        controller = GuardedController.from_config(
            backend, args.actions, authorized=args.authorized
        )
        result = run_desktop(
            capture,
            PixelPerception(),
            RuleBasedPolicy(),
            controller,
            args.output,
            max_seconds=args.seconds,
        )
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1
    elif args.command == "compare":
        from uga.core.contracts import EvaluationResult
        from uga.evaluation.experiments import compare

        result = compare(
            EvaluationResult.model_validate_json(args.baseline.read_text(encoding="utf-8")),
            EvaluationResult.model_validate_json(args.candidate.read_text(encoding="utf-8")),
        )
        print(json.dumps(result, indent=2))
        return 0 if result["eligible"] else 1
    elif args.command == "soak":
        import signal
        import threading

        from uga.supervisor.long_run import FileCancellation
        from uga.supervisor.soak import run_soak

        cancelled = threading.Event()

        def request_stop(signum, frame):
            cancelled.set()

        previous = {
            sig: signal.signal(sig, request_stop) for sig in (signal.SIGINT, signal.SIGTERM)
        }
        try:
            result = run_soak(
                args.seconds,
                args.output,
                cancel=FileCancellation(args.output / "cancel.json", cancelled),
            )
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    elif args.command == "soak-service":
        from uga.supervisor.long_run import LongRunManager

        manager = LongRunManager(args.output)
        result = (
            manager.start(args.seconds)
            if args.action == "start"
            else manager.stop()
            if args.action == "stop"
            else manager.status()
        )
        print(json.dumps(result, indent=2))
    elif args.command == "builder":
        from uga.agents.builder.agent import generate, parse_requirements

        if args.export_preset and not args.validate:
            raise ValueError("--export-preset requires --validate")
        if args.validate and not args.allow_external_tools:
            from uga.core.errors import AuthorizationRequired

            raise AuthorizationRequired("Godot validation requires --allow-external-tools")
        result = generate(parse_requirements(args.requirements), args.output)
        if args.validate:
            from uga.agents.builder.pipeline import validate_project

            result["engine"] = validate_project(
                args.output,
                args.output.parent / (args.output.name + "-validation"),
                approved=args.allow_external_tools,
                export_preset=args.export_preset,
            )
            result["built"] = "export" in result["engine"]
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "reverse":
        from uga.agents.reverse.agent import analyze

        print(analyze(args.path, args.output, authorized=args.authorized).model_dump_json(indent=2))
    elif args.command == "reverse-tool":
        from uga.agents.reverse.tool_analysis import analyze_with_tool

        result = analyze_with_tool(
            args.tool,
            args.path,
            args.output,
            approved=args.allow_external_tools,
            authorized=args.authorized,
            trusted_input=args.trusted_input,
            executable=args.executable,
            java=args.java,
            installation=args.installation,
        )
        print(result.model_dump_json(indent=2))
    elif args.command in ("builder-edit", "builder-repair"):
        from uga.agents.builder.revision import PatchPlan, repair_project, revise_project

        if args.command == "builder-edit":
            if args.patch.stat().st_size > 8_000_000:
                raise ValueError("patch plan exceeds 8 MB")
            plan = PatchPlan.model_validate_json(args.patch.read_text(encoding="utf-8"))
            result = revise_project(
                args.source,
                args.output,
                plan,
                authorized=args.authorized,
                approved=args.allow_external_tools,
                validate=args.validate,
            )
        else:
            result = repair_project(
                args.source,
                args.output,
                authorized=args.authorized,
                approved=args.allow_external_tools,
            )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "workflow":
        from uga.workflows import build_play

        print(
            json.dumps(
                build_play(
                    args.requirements,
                    args.output,
                    backend=args.backend,
                    approved=args.allow_external_tools,
                    export_preset=args.export_preset,
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
    elif args.command == "rebuild":
        from uga.workflows import reverse_build_play

        print(
            json.dumps(
                reverse_build_play(
                    args.source,
                    args.output,
                    authorized=args.authorized,
                    backend=args.backend,
                    approved=args.allow_external_tools,
                    export_preset=args.export_preset,
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
    elif args.command == "improve":
        from uga.evaluation.benchmark import run_benchmark
        from uga.evaluation.experiments import ExperimentManager
        from uga.memory.store import Store, atomic_json

        baseline = run_benchmark(
            args.output / "baseline",
            attack_range=args.baseline_range,
            navigation_mode=args.baseline_mode,
        )
        candidate = run_benchmark(
            args.output / "candidate",
            attack_range=args.candidate_range,
            navigation_mode=args.candidate_mode,
        )
        result = ExperimentManager(Store(args.state_dir)).propose(baseline, candidate)
        atomic_json(args.output / "proposal.json", result)
        print(json.dumps(result, indent=2))
        return 0 if result["comparison"]["eligible"] else 1
    elif args.command == "experiment":
        from uga.core.contracts import EvaluationResult
        from uga.evaluation.experiments import ExperimentManager
        from uga.memory.store import Store

        manager = ExperimentManager(Store(args.state_dir))
        if args.action == "list":
            result = manager.store.list_checkpoints("experiment:")
        elif args.action == "approve":
            if not args.id:
                raise ValueError("--id is required")
            result = manager.promote(args.id, approved=args.approve)
        elif args.action == "monitor":
            if not args.report:
                raise ValueError("--report is required")
            result = manager.monitor(
                EvaluationResult.model_validate_json(args.report.read_text(encoding="utf-8"))
            )
        else:
            result = manager.rollback()
        print(json.dumps(result, indent=2))
    elif args.command == "mcp":
        from uga.integrations.mcp import MCPAdapter
        from uga.orchestrator.jobs import Orchestrator

        with Orchestrator(args.state_dir, analysis_root=args.analysis_root) as jobs:
            MCPAdapter(jobs).serve()
    elif args.command.startswith("godot-"):
        from uga.agents.builder.godot import GodotAdapter

        adapter = GodotAdapter()
        if args.command == "godot-check":
            result = {
                "validation": adapter.validate(args.project, approved=args.allow_external_tools),
                "smoke": adapter.smoke(
                    args.project, args.output, approved=args.allow_external_tools
                ),
            }
        elif args.command == "godot-play":
            result = adapter.play(
                args.project,
                args.output,
                approved=args.allow_external_tools,
                seed=args.seed,
                game_executable=args.game_executable,
            )
        else:
            result = adapter.export(
                args.project, args.preset, args.output, approved=args.allow_external_tools
            )
        print(json.dumps(result, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    import sys

    from uga.core.errors import UGAError

    try:
        return _main(argv)
    except (UGAError, ValueError, OSError, KeyError) as exc:
        print(f"uga: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
