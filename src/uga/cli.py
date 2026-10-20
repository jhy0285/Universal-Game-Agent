import argparse
import json
from pathlib import Path

from uga.capabilities import capabilities
from uga.core.contracts import CONTRACTS


def main(argv: list[str] | None = None) -> int:
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
    player = commands.add_parser("player", help="Play the reference test arena from pixels")
    player.add_argument("--seed", type=int, default=7)
    player.add_argument("--max-steps", type=int, default=600)
    player.add_argument("--attack-range", type=float)
    player.add_argument("--output", type=Path, default=Path(".uga/player"))
    benchmark = commands.add_parser("benchmark", help="Run the fixed-seed pixel benchmark")
    benchmark.add_argument("--attack-range", type=float, default=14)
    benchmark.add_argument("--output", type=Path, default=Path(".uga/benchmark"))
    comparison = commands.add_parser("compare", help="Compare reports under identical conditions")
    comparison.add_argument("baseline", type=Path)
    comparison.add_argument("candidate", type=Path)
    soak = commands.add_parser("soak", help="Real wall-clock repeated-play health test")
    soak.add_argument("--seconds", type=float, default=1800)
    soak.add_argument("--output", type=Path, default=Path(".uga/soak"))
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
    elif args.command == "serve":
        import uvicorn

        from uga.api import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port)
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
            ArenaConfig(seed=args.seed, max_steps=args.max_steps),
            RuleBasedPolicy(attack_range),
            args.output,
        )
        print(result.model_dump_json(indent=2))
        return 0 if result.success else 1
    elif args.command == "benchmark":
        from uga.evaluation.benchmark import run_benchmark

        result = run_benchmark(args.output, attack_range=args.attack_range)
        print(result.model_dump_json(indent=2))
        return 0 if result.passed else 1
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
        from uga.supervisor.soak import run_soak

        result = run_soak(args.seconds, args.output)
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
