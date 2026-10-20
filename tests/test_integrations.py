import io
import json

import pytest

from uga.agents.reverse.adapters import GhidraAdapter, REAAdapter
from uga.core.errors import AuthorizationRequired
from uga.integrations.mcp import MCPAdapter
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
