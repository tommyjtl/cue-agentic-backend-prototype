from fastapi.testclient import TestClient

from cue.config import settings
from cue_server.main import app


def test_public_scanner_paths_are_blocked(monkeypatch):
    monkeypatch.setattr(settings, "public_strict_routes", True)
    monkeypatch.setattr(settings, "public_expose_health", False)

    client = TestClient(app)
    response = client.get(
        "/config.json",
        headers={"X-Forwarded-For": "159.65.18.197"},
    )
    assert response.status_code == 404


def test_public_webhook_path_is_allowed(monkeypatch):
    monkeypatch.setattr(settings, "public_strict_routes", True)
    monkeypatch.setattr(settings, "linq_api_key", "")
    monkeypatch.setattr(settings, "linq_webhook_secret", "")

    client = TestClient(app)
    response = client.post(
        "/v1/linq/webhook",
        json={},
        headers={"X-Forwarded-For": "54.157.59.12"},
    )
    assert response.status_code == 503


def test_localhost_can_reach_search(monkeypatch):
    monkeypatch.setattr(settings, "public_strict_routes", True)

    client = TestClient(app)
    response = client.post(
        "/v1/search",
        json={
            "query": "test",
            "corpus_root": "/tmp",
            "llm": {
                "provider": "ollama",
                "base_url": "http://localhost:11434",
                "model": "test",
            },
        },
    )
    assert response.status_code != 404
