"""Minimal local MCP stdio adapter, protocol 2025-06-18; no external AI connection."""

import json
import sys

from uga import __version__
from uga.core.contracts import TaskSpec

TASK_SCHEMA = TaskSpec.model_json_schema()
TASK_DEFINITIONS = TASK_SCHEMA.pop("$defs", {})

TOOLS = [
    {
        "name": "uga_submit_task",
        "description": "Submit a registered authorized UGA job",
        "inputSchema": {
            "type": "object",
            "properties": {"task": TASK_SCHEMA},
            "$defs": TASK_DEFINITIONS,
            "required": ["task"],
            "additionalProperties": False,
        },
    },
    {
        "name": "uga_job_status",
        "description": "Read persistent job status",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "uga_cancel_task",
        "description": "Cancel a UGA-owned queued or running job",
        "inputSchema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
            "additionalProperties": False,
        },
    },
]


class MCPAdapter:
    def __init__(self, orchestrator):
        self.jobs = orchestrator

    def dispatch(self, request):
        if (
            not isinstance(request, dict)
            or request.get("jsonrpc") != "2.0"
            or not isinstance(request.get("method"), str)
        ):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request"},
            }
        if "id" not in request:
            return None
        identity = request["id"]
        method = request["method"]
        if method == "initialize":
            result = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "uga", "version": __version__},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            try:
                params = request["params"]
                args = params.get("arguments", {})
                name = params["name"]
                if name == "uga_submit_task":
                    value = self.jobs.submit(TaskSpec.model_validate(args["task"]))
                elif name == "uga_job_status":
                    value = self.jobs.store.task(args["task_id"])
                elif name == "uga_cancel_task":
                    value = self.jobs.cancel(args["task_id"])
                else:
                    raise ValueError("unknown UGA tool")
                result = {
                    "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
                    "isError": False,
                }
            except Exception as exc:
                result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        else:
            return {
                "jsonrpc": "2.0",
                "id": identity,
                "error": {"code": -32601, "message": "Method not found"},
            }
        return {"jsonrpc": "2.0", "id": identity, "result": result}

    def serve(self, source=None, sink=None):
        source = source or sys.stdin
        sink = sink or sys.stdout
        while True:
            line = source.readline(1_000_001)
            if not line:
                break
            try:
                if len(line) > 1_000_000:
                    raise ValueError("message exceeds 1 MiB")
                result = self.dispatch(json.loads(line))
            except ValueError:
                result = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error or oversized message"},
                }
            if result is not None:
                sink.write(json.dumps(result, ensure_ascii=False) + "\n")
                sink.flush()
