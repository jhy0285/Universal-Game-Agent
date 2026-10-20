from fastapi.testclient import TestClient

from uga.api import create_app


def test_health_contracts_and_capabilities():
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert len(client.get("/api/v1/contracts").json()) == 7
        info = client.get("/api/v1/capabilities").json()
        assert info["cpu_fallback"] is True
        assert info["laya"]["available"] is False
