"""Functional check against the owned local service; never print its capability token."""

import argparse
import http.client
import json
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, default=Path(".uga"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    token = (args.state_dir / "api-token").read_text(encoding="utf-8")

    def request(method, path, payload=None):
        connection = http.client.HTTPConnection("127.0.0.1", args.port, timeout=5)
        headers = {"X-UGA-Token": token}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        connection.request(
            method, path, json.dumps(payload) if payload is not None else None, headers
        )
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}: {raw[:200]!r}")
        return json.loads(raw)

    assert request("GET", "/health")["status"] == "ok"
    job = request(
        "POST", "/api/v1/jobs", {"agent": "player", "operation": "play", "parameters": {"seed": 7}}
    )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        row = request("GET", "/api/v1/jobs/" + job["id"])
        if row["status"] not in ("queued", "running"):
            assert row["status"] == "succeeded", row
            assert row["result"]["success"] is True, row
            print(
                json.dumps(
                    {"http_smoke": "passed", "task_id": job["id"], "steps": row["result"]["steps"]}
                )
            )
            return 0
        time.sleep(0.05)
    raise TimeoutError("local service did not complete a real player episode")


if __name__ == "__main__":
    raise SystemExit(main())
