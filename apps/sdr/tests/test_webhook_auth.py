"""Webhook auth tests (no live DB)."""

from __future__ import annotations


def test_webhook_401_without_secret(client) -> None:
    response = client.post("/webhook/evolution", json={"event": "messages.upsert"})
    assert response.status_code == 401


def test_webhook_200_with_x_sdr_secret(client, webhook_secret: str) -> None:
    response = client.post(
        "/webhook/evolution",
        json={"event": "messages.upsert"},
        headers={"x-sdr-secret": webhook_secret},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["accepted"] is True


def test_webhook_200_with_authorization_bearer(client, webhook_secret: str) -> None:
    response = client.post(
        "/webhook/evolution",
        json={"event": "messages.upsert"},
        headers={"Authorization": f"Bearer {webhook_secret}"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
