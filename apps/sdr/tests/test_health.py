"""Health endpoint tests."""

from __future__ import annotations


def test_health_returns_200(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert "julia_enabled" in payload
    assert isinstance(payload["julia_enabled"], bool)
