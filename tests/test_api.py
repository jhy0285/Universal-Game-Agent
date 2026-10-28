import hashlib
import os
import time

from fastapi.testclient import TestClient

from uga.api import create_app, token_matches


def test_health_contracts_and_capabilities(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert len(client.get("/api/v1/contracts").json()) == 7
        info = client.get("/api/v1/capabilities").json()
        assert info["cpu_fallback"] is True
        assert info["laya"]["available"] is False


def wait(client, identity):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        row = client.get(f"/api/v1/jobs/{identity}").json()
        if row["status"] not in ("queued", "running"):
            return row
        time.sleep(0.025)
    raise AssertionError("HTTP job did not complete")


def test_dashboard_and_local_authorization(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200 and app.state.token not in page.text
        token_file = tmp_path / "api-token"
        assert token_file.read_text(encoding="utf-8") == app.state.token
        if os.name != "nt":
            assert token_file.stat().st_mode & 0o077 == 0
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/static/style.css").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/api/v1/jobs").status_code == 401
        client.headers["X-UGA-Token"] = app.state.token
        assert client.get("/api/v1/system").json()["gpu"] is None
        assert client.get("/api/v1/agents").json()["player"]["operations"] == ["play", "soak"]
        assert (
            client.post(
                "/api/v1/jobs",
                json={"agent": "player", "operation": "play"},
                headers={"Origin": "https://untrusted.example"},
            ).status_code
            == 403
        )
        assert client.get("/health", headers={"Host": "untrusted.example"}).status_code == 400
        assert (
            client.post(
                "/api/v1/jobs",
                json={"task_id": "../escape", "agent": "player", "operation": "play"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/jobs",
                json={
                    "agent": "player",
                    "operation": "play",
                    "parameters": {"allow_external": True},
                },
            ).status_code
            == 422
        )


def test_non_ascii_token_headers_are_rejected_not_crashed(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        non_ascii = "café".encode("latin-1")
        for headers in (
            {"X-UGA-Token": non_ascii},
            {"Authorization": b"Bearer " + non_ascii},
        ):
            response = client.get("/api/v1/jobs", headers=headers)
            assert response.status_code == 401, headers
            assert response.json() == {"detail": "local capability token required"}
        assert (
            client.get("/api/v1/jobs", headers={"X-UGA-Token": app.state.token}).status_code == 200
        )
        bearer = {"Authorization": "Bearer " + app.state.token}
        assert client.get("/api/v1/jobs", headers=bearer).status_code == 200


def test_token_matches_handles_unencodable_and_missing_values():
    assert token_matches("abc", "abc")
    assert not token_matches("abd", "abc")
    assert not token_matches("café", "abc")
    assert not token_matches("\ud800", "abc")
    assert not token_matches("abc", None)
    assert not token_matches("", "")


def test_http_build_analyze_play_cancel_and_artifact_integrity(tmp_path):
    app = create_app(tmp_path / "state", analysis_root=tmp_path)
    with TestClient(app) as client:
        client.headers["X-UGA-Token"] = app.state.token
        created = client.post(
            "/api/v1/jobs",
            json={
                "agent": "builder",
                "operation": "generate",
                "parameters": {"requirements": "enemies 2"},
            },
        )
        assert created.status_code == 202, created.text
        builder = wait(client, created.json()["id"])
        assert builder["status"] == "succeeded", builder
        created = client.post(
            "/api/v1/jobs",
            json={
                "agent": "reverse",
                "operation": "analyze",
                "authorized": True,
                "parameters": {"path": builder["result"]["project"]},
            },
        )
        reverse = wait(client, created.json()["id"])
        assert reverse["status"] == "succeeded" and reverse["result"]["findings"]
        cloned = client.post(
            "/api/v1/jobs",
            json={
                "agent": "builder",
                "operation": "generate",
                "parameters": {"spec": reverse["result"]},
            },
        )
        cloned = wait(client, cloned.json()["id"])
        assert (
            cloned["status"] == "succeeded" and cloned["result"]["spec"]["combat"]["enemies"] == 2
        )
        created = client.post(
            "/api/v1/jobs",
            json={"agent": "player", "operation": "play", "parameters": {"seed": 19}},
        )
        identity = created.json()["id"]
        player = wait(client, identity)
        assert player["result"]["success"]
        assert client.get(f"/api/v1/jobs/{identity}/preview").content.startswith(b"\x89PNG")
        artifacts = client.get(f"/api/v1/jobs/{identity}/artifacts").json()
        assert artifacts
        reference = artifacts[0]["reference"]
        content = client.get("/api/v1/artifacts/" + reference["artifact_id"]).content
        assert hashlib.sha256(content).hexdigest() == reference["sha256"]
        assert any(e["event"] == "succeeded" for e in client.get("/api/v1/events").json())
        created = client.post(
            "/api/v1/jobs",
            json={"agent": "player", "operation": "soak", "parameters": {"seconds": 60}},
        )
        assert client.post("/api/v1/stop", json={}).status_code == 200
        assert wait(client, created.json()["id"])["status"] == "cancelled"
