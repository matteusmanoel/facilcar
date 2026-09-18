"""Phase 13A-R1 — Python Evolution webhook must honor phone access before Redis."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from sdr.config import get_settings
from sdr.main import create_app

ALLOWED = "5511999000101"
DENIED = "5511999000199"
SECRET = "test-sdr-secret"


class FakeRedis:
    def __init__(self) -> None:
        self.ops: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def set(self, *args: Any, **kwargs: Any) -> None:
        self.ops.append(("set", args, kwargs))

    async def aclose(self) -> None:
        return None


def _app_with_redis(monkeypatch: pytest.MonkeyPatch, fake: FakeRedis) -> TestClient:
    async def _init(_settings=None):
        return fake

    monkeypatch.setattr("sdr.redis_client.init_redis", _init)
    monkeypatch.setattr("sdr.redis_client.get_redis", lambda: fake)
    monkeypatch.setattr("sdr.api.webhook.get_redis", lambda: fake)
    monkeypatch.setenv("SDR_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("SDR_ENVIRONMENT", "staging")
    monkeypatch.setenv("SDR_OUTBOUND_POLICY", "allowlist")
    monkeypatch.setenv("SDR_OUTBOUND_ALLOWLIST", ALLOWED)
    monkeypatch.setenv("SDR_DOCUMENTS_BUCKET", "sdr-documents-test")
    get_settings.cache_clear()
    return TestClient(create_app())


def _payload(jid: str | None, *, from_me: bool = False, event: str = "messages.upsert") -> dict[str, Any]:
    data: dict[str, Any] = {"key": {"fromMe": from_me}}
    if jid is not None:
        data["key"]["remoteJid"] = jid
    return {"event": event, "data": data}


def test_denied_phone_does_not_mark_debounce_or_call_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    with _app_with_redis(monkeypatch, fake) as client:
        response = client.post(
            "/webhook/evolution",
            json=_payload(f"{DENIED}@s.whatsapp.net"),
            headers={"x-sdr-secret": SECRET},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["accepted"] is True
    assert body["processed"] is False
    assert body["debounce_marked"] is False
    assert "ignor" in body["message"].lower()
    assert DENIED not in response.text
    assert fake.ops == []


def test_missing_phone_has_no_redis_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    with _app_with_redis(monkeypatch, fake) as client:
        response = client.post(
            "/webhook/evolution",
            json=_payload(None),
            headers={"x-sdr-secret": SECRET},
        )
    assert response.status_code == 200
    assert response.json()["debounce_marked"] is False
    assert fake.ops == []


def test_allowed_phone_may_mark_debounce(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    with _app_with_redis(monkeypatch, fake) as client:
        response = client.post(
            "/webhook/evolution",
            json=_payload(f"{ALLOWED}@s.whatsapp.net"),
            headers={"x-sdr-secret": SECRET},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["debounce_marked"] is True
    assert fake.ops
    assert any("set" == op[0] for op in fake.ops)


def test_fromme_and_group_events_remain_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    with _app_with_redis(monkeypatch, fake) as client:
        from_me = client.post(
            "/webhook/evolution",
            json=_payload(f"{ALLOWED}@s.whatsapp.net", from_me=True),
            headers={"x-sdr-secret": SECRET},
        )
        group = client.post(
            "/webhook/evolution",
            json=_payload("120363012345678901@g.us"),
            headers={"x-sdr-secret": SECRET},
        )
        other = client.post(
            "/webhook/evolution",
            json={"event": "connection.update", "data": {}},
            headers={"x-sdr-secret": SECRET},
        )
    assert from_me.status_code == 200
    assert group.status_code == 200
    assert other.status_code == 200
    assert other.json()["debounce_marked"] is False
