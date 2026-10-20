import time

import pytest
from fastapi.testclient import TestClient

from uga.api import create_app


def wait(client, identity):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        row = client.get(f"/api/v1/jobs/{identity}").json()
        if row["status"] not in ("queued", "running"):
            return row
        time.sleep(0.025)
    raise AssertionError("Godot HTTP job did not complete")


@pytest.mark.external
def test_http_engine_jobs_require_authorization_and_pass_spec(approved_godot, tmp_path):
    root = tmp_path / "state"
    app = create_app(root, analysis_root=tmp_path)
    with TestClient(app) as client:
        client.headers["X-UGA-Token"] = app.state.token
        request = {
            "agent": "workflow",
            "operation": "build-play",
            "parameters": {"requirements": "2 enemies", "backend": "godot"},
        }
        assert client.post("/api/v1/jobs", json=request).status_code == 403
        request["authorized"] = True
        created = client.post("/api/v1/jobs", json=request)
        assert created.status_code == 202, created.text
        first = wait(client, created.json()["id"])
        assert first["status"] == "succeeded", first
        assert first["result"]["godot_executed"]
        assert first["result"]["engine"]["player"]["success"]
        created = client.post(
            "/api/v1/jobs",
            json={
                "agent": "workflow",
                "operation": "reverse-build-play",
                "authorized": True,
                "parameters": {"path": first["result"]["generated"]["project"], "backend": "godot"},
            },
        )
        second = wait(client, created.json()["id"])
        assert second["status"] == "succeeded", second
        assert second["result"]["generated"]["spec"]["combat"]["enemies"] == 2
        assert second["result"]["engine"]["player"]["success"]
        created = client.post(
            "/api/v1/jobs",
            json={
                "agent": "builder",
                "operation": "build",
                "authorized": True,
                "parameters": {"spec": first["result"]["analysis"]},
            },
        )
        builder = wait(client, created.json()["id"])
        assert builder["status"] == "succeeded", builder
        assert builder["result"]["engine"]["smoke"]["passed"]
