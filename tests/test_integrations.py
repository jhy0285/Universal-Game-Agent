import asyncio
import io
import json
from pathlib import Path

import pytest

from uga.agents.reverse.adapters import AsyncREAAdapter, GhidraAdapter, REAAdapter
from uga.core.errors import AuthorizationRequired
from uga.integrations.mcp import MCPAdapter
from uga.integrations.process import ToolResult
from uga.orchestrator.jobs import Orchestrator


def test_rea_uses_discovered_tools_and_keeps_evidence_uninterpreted():
    class Transport:
        def list_tools(self):
            return [{"name": "verified_tool", "inputSchema": {"type": "object"}}]

        def call_tool(self, name, arguments):
            return {"content": [{"type": "text", "text": "evidence"}]}

    adapter = REAAdapter(Transport())
    with pytest.raises(AuthorizationRequired):
        adapter.invoke("verified_tool", {})
    with pytest.raises(ValueError):
        adapter.invoke("invented_tool", {}, authorized=True)
    assert adapter.invoke("verified_tool", {}, authorized=True)["mechanics_verified"] is False


def test_external_analyzer_requires_trusted_scope(tmp_path):
    adapter = GhidraAdapter(tmp_path / "not-run")
    with pytest.raises(AuthorizationRequired, match="sandbox"):
        adapter.analyze(tmp_path / "sample", tmp_path / "out", approved=True, authorized=True)


def test_ghidra_uses_a_nonhidden_temporary_project_and_retains_evidence(tmp_path, monkeypatch):
    projects = []

    def execute(command, cwd, **options):
        projects.append(Path(command[1]))
        assert not any(part.startswith(".") for part in projects[-1].parts)
        report = Path(command[command.index("-postScript") + 2])
        report.write_text('{"functions": []}')
        return ToolResult(command, 0, "unit fixture", 0.01)

    monkeypatch.setattr("uga.agents.reverse.adapters.run_tool", execute)
    sample = tmp_path / "owned"
    sample.write_bytes(b"fixture")
    output = tmp_path / ".uga" / "analysis"
    result = GhidraAdapter(tmp_path / "not-executed").analyze(
        sample,
        output,
        approved=True,
        authorized=True,
        trusted_input=True,
    )
    assert result["analyzed"] and (output / "functions.json").exists()
    assert not projects[0].exists()


def test_async_rea_only_invokes_discovered_authorized_tools():
    class Transport:
        async def list_tools(self):
            return [{"name": "read_fixture", "inputSchema": {"type": "object"}}]

        async def call_tool(self, name, arguments):
            return {"content": [{"type": "text", "text": "fixture"}], "isError": False}

    async def run():
        adapter = AsyncREAAdapter(Transport())
        with pytest.raises(AuthorizationRequired):
            await adapter.invoke("read_fixture", {})
        with pytest.raises(ValueError):
            await adapter.invoke("unknown", {}, authorized=True)
        result = await adapter.invoke("read_fixture", {}, authorized=True)
        assert not result["mechanics_verified"] and result["tool"] == "read_fixture"

    asyncio.run(run())


def test_mcp_initialize_discovery_and_job_calls(tmp_path):
    with Orchestrator(tmp_path) as jobs:
        adapter = MCPAdapter(jobs)
        result = adapter.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert result["result"]["protocolVersion"] == "2025-06-18"
        tools = adapter.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert len(tools["result"]["tools"]) == 3
        response = adapter.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "uga_submit_task",
                    "arguments": {"task": {"agent": "player", "operation": "play"}},
                },
            }
        )
        row = json.loads(response["result"]["content"][0]["text"])
        assert row["spec"]["agent"] == "player"
        assert adapter.dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
        sink = io.StringIO()
        adapter.serve(io.StringIO("{invalid}\n"), sink)
        assert json.loads(sink.getvalue())["error"]["code"] == -32700
