"""Read-only REA MCP interoperability against an explicitly authorized local fixture."""

import argparse
import asyncio
import hashlib
import json
import shutil
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# The SDK is isolated in a verification venv; import the checked-out UGA adapter explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uga.agents.reverse.adapters import AsyncREAAdapter  # noqa: E402


async def validate(args):
    if not args.allow_external_tools or not args.authorized:
        raise ValueError("REA execution and fixture analysis both need authorization")
    if args.output.exists() or args.sample.is_symlink() or not args.sample.is_file():
        raise ValueError("Use a regular authorized sample and a new report path")
    digest = hashlib.sha256(args.sample.read_bytes()).hexdigest()
    params = StdioServerParameters(
        command=shutil.which("node"),
        args=[str(args.rea_script.resolve()), "mcp"],
        env={"REA_PWNTOOLS_PYTHON": str(args.pwntools_python.absolute())}
        if args.pwntools_python
        else None,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()

            class Transport:
                async def list_tools(self):
                    discovery = await session.list_tools()
                    return [tool.model_dump(by_alias=True) for tool in discovery.tools]

                async def call_tool(self, name, arguments):
                    raw = (await session.call_tool(name, arguments)).model_dump(by_alias=True)
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.with_suffix(".last-tool.json").write_text(json.dumps(raw, indent=2))
                    return raw

            adapter = AsyncREAAdapter(Transport())
            tools = await adapter.tools()
            result = await adapter.invoke(
                "inspect_binary_layout",
                {"path": str(args.sample.resolve())},
                authorized=True,
            )
            raw = result["raw_evidence"]
            evidence = raw.get("structuredContent")
            if evidence is None:
                evidence = json.loads(raw["content"][0]["text"])
            assert evidence["subject"]["digest"]["sha256"] == digest, evidence
            result.update(
                initialized=initialized.model_dump(by_alias=True),
                discovered_tool_count=len(tools),
                target_sha256=digest,
                executed_target=False,
                external_ai_connected=False,
                passed=True,
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps({"passed": True, "tools": len(tools), "target_sha256": digest}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rea-script", type=Path, required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--pwntools-python", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorized", action="store_true")
    parser.add_argument("--allow-external-tools", action="store_true")
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(validate(args), timeout=30))


if __name__ == "__main__":
    main()
