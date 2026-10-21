"""Explicit real analyzer jobs over the owned API, using only original UGA fixtures."""

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-external-tools", action="store_true")
    parser.add_argument("--state-dir", type=Path, default=Path(".uga"))
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not args.allow_external_tools or args.output.exists():
        raise ValueError("Explicit analyzer approval and a new report path are required")
    token = (args.state_dir / "api-token").read_text().strip()

    def request(path, body=None):
        call = urllib.request.Request(
            f"http://127.0.0.1:{args.port}/api/v1/{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"X-UGA-Token": token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(call, timeout=15) as response:
            return response.read()

    results = []
    for tool, filename, expected in (
        ("jadx", "CombatRules.class", {"clampHp", "applyDamage", "usePotion"}),
        ("ghidra", "combat", {"clamp_hp", "apply_damage", "use_potion"}),
    ):
        sample = (args.input_dir / filename).resolve()
        assert sample.is_file()
        parameters = {"tool": tool, "path": str(sample), "trusted_input": False}
        task = {
            "agent": "reverse",
            "operation": "decompile",
            "authorized": True,
            "parameters": parameters,
        }
        try:
            request("jobs", task)
            raise AssertionError("untrusted native analysis was accepted")
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
        parameters["trusted_input"] = True
        row = json.loads(request("jobs", task))
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            row = json.loads(request("jobs/" + row["id"]))
            if row["status"] not in ("queued", "running"):
                break
            time.sleep(0.1)
        assert row["status"] == "succeeded", row
        assert expected <= {finding["subject"] for finding in row["result"]["findings"]}
        assert row["result"]["genre"] is None
        artifacts = json.loads(request(f"jobs/{row['id']}/artifacts"))
        for artifact in artifacts:
            reference = artifact["reference"]
            data = request("artifacts/" + reference["artifact_id"])
            assert len(data) == reference["size_bytes"]
            assert hashlib.sha256(data).hexdigest() == reference["sha256"]
        results.append(
            {
                "tool": tool,
                "id": row["id"],
                "status": row["status"],
                "functions": sorted(expected),
                "verified_artifacts": len(artifacts),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"passed": True, "jobs": results, "executed_target": False}, indent=2) + "\n"
    )
    print(json.dumps({"passed": True, "tools": [result["tool"] for result in results]}))


if __name__ == "__main__":
    main()
