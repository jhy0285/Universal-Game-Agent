"""Authorized real engine job over the owned loopback API; never print its token."""

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-external-tools", action="store_true")
    parser.add_argument("--state-dir", type=Path, default=Path(".uga"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_external_tools:
        raise ValueError("Godot execution needs --allow-external-tools")
    if args.output.exists():
        raise FileExistsError("Use a new HTTP validation result path")
    token = (args.state_dir / "api-token").read_text().strip()

    def request(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        call = urllib.request.Request(
            f"http://127.0.0.1:{args.port}{path}",
            data=data,
            headers={"X-UGA-Token": token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(call, timeout=10) as response:
            return response.read()

    created = json.loads(
        request(
            "/api/v1/jobs",
            {
                "agent": "workflow",
                "operation": "build-play",
                "authorized": True,
                "parameters": {"requirements": "2 enemies", "backend": "godot"},
            },
        )
    )
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        row = json.loads(request("/api/v1/jobs/" + created["id"]))
        if row["status"] not in ("queued", "running"):
            break
        time.sleep(0.1)
    assert row["status"] == "succeeded", row
    assert row["result"]["godot_executed"] and row["result"]["engine"]["player"]["success"]
    artifacts = json.loads(request(f"/api/v1/jobs/{created['id']}/artifacts"))
    for entry in artifacts:
        reference = entry["reference"]
        data = request("/api/v1/artifacts/" + reference["artifact_id"])
        assert len(data) == reference["size_bytes"]
        assert hashlib.sha256(data).hexdigest() == reference["sha256"]
    result = {
        "passed": True,
        "job_id": row["id"],
        "status": row["status"],
        "enemy_count": row["result"]["analysis"]["combat"]["enemies"],
        "godot_executed": True,
        "player": row["result"]["engine"]["player"],
        "smoke": row["result"]["engine"]["smoke"],
        "verified_artifacts": len(artifacts),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "job_id": row["id"], "verified_artifacts": len(artifacts)}))


if __name__ == "__main__":
    main()
