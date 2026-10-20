"""Official SDK interoperability; local UGA stdio only, no AI provider connection."""

import argparse
import asyncio
import json
from importlib.metadata import version
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def payload(result):
    if getattr(result, "is_error", getattr(result, "isError", False)):
        raise AssertionError("MCP tool returned an error")
    return json.loads(result.content[0].text)


async def validate(python: Path, output: Path):
    if output.exists():
        raise FileExistsError("Use a new MCP validation directory")
    output.mkdir(parents=True)
    parameters = StdioServerParameters(
        command=str(python.absolute()),
        args=["-m", "uga.cli", "mcp", "--state-dir", str((output / "state").resolve())],
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            discovery = await session.list_tools()
            names = [tool.name for tool in discovery.tools]
            assert set(names) == {"uga_submit_task", "uga_job_status", "uga_cancel_task"}
            player = payload(
                await session.call_tool(
                    "uga_submit_task",
                    {
                        "task": {"agent": "player", "operation": "play", "parameters": {"seed": 7}},
                    },
                )
            )
            for _ in range(200):
                player = payload(
                    await session.call_tool("uga_job_status", {"task_id": player["id"]})
                )
                if player["status"] not in ("queued", "running"):
                    break
                await asyncio.sleep(0.05)
            assert player["status"] == "succeeded" and player["result"]["success"], player
            queued = payload(
                await session.call_tool(
                    "uga_submit_task",
                    {
                        "task": {
                            "agent": "player",
                            "operation": "soak",
                            "parameters": {"seconds": 60},
                        },
                    },
                )
            )
            cancelled = payload(
                await session.call_tool("uga_cancel_task", {"task_id": queued["id"]})
            )
            assert cancelled["status"] == "cancelled", cancelled
            result = {
                "sdk": "official modelcontextprotocol/python-sdk",
                "sdk_version": version("mcp"),
                "negotiated_protocol": getattr(
                    initialized, "protocol_version", getattr(initialized, "protocolVersion", None)
                ),
                "tools": names,
                "player": player,
                "cancelled_task_status": cancelled["status"],
                "external_ai_connected": False,
                "passed": True,
            }
            (output / "results.json").write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
            print(
                json.dumps(
                    {
                        "passed": True,
                        "sdk_version": result["sdk_version"],
                        "protocol": result["negotiated_protocol"],
                    }
                )
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--python", type=Path, required=True, help="UGA venv Python, preserving its venv path"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(validate(args.python, args.output), timeout=30))


if __name__ == "__main__":
    main()
