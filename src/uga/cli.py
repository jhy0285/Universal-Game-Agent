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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
