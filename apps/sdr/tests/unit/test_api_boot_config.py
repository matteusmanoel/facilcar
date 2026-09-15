"""Phase 13A-R1 — API process validates runtime config at lifecycle startup."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sdr.config import get_settings
from sdr.main import create_app
from sdr.redis_client import get_redis


def _neutral_env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    monkeypatch.setenv("SDR_ENVIRONMENT", "sandbox")
    monkeypatch.setenv("SDR_OUTBOUND_POLICY", "deny_all")
    monkeypatch.setenv("SDR_OUTBOUND_ALLOWLIST", "")
    monkeypatch.setenv("SDR_DOCUMENTS_BUCKET", "")
    monkeypatch.setenv("STORAGE_ENDPOINT", "")
    monkeypatch.setenv("STORAGE_ACCESS_KEY", "")
    monkeypatch.setenv("STORAGE_SECRET_KEY", "")
    monkeypatch.setenv("SDR_WEBHOOK_SECRET", "test-sdr-secret")
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def test_valid_sandbox_boots_and_ready_config_is_200(monkeypatch: pytest.MonkeyPatch) -> None:
    redis_inits = {"n": 0}

    async def _init(_settings=None):
        redis_inits["n"] += 1
        return object()

    async def _close() -> None:
        return None

    monkeypatch.setattr("sdr.redis_client.init_redis", _init)
    monkeypatch.setattr("sdr.redis_client.close_redis", _close)
    _neutral_env(monkeypatch)
    app = create_app()
    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready/config")
    assert health.status_code == 200
    assert ready.status_code == 200
    body = ready.json()
    assert body["ok"] is True
    assert body["ready"] is True
    assert body["dependencies_checked"] is False


def test_invalid_staging_does_not_start_operational(monkeypatch: pytest.MonkeyPatch) -> None:
    redis_inits = {"n": 0}

    async def _init(_settings=None):
        redis_inits["n"] += 1
        raise AssertionError("Redis must not initialize when config is invalid")

    monkeypatch.setattr("sdr.redis_client.init_redis", _init)
    _neutral_env(
        monkeypatch,
        SDR_ENVIRONMENT="staging",
        SDR_OUTBOUND_POLICY="allowlist",
        SDR_OUTBOUND_ALLOWLIST="",
        SDR_DOCUMENTS_BUCKET="",
        SDR_WEBHOOK_SECRET="not-a-placeholder",
    )
    app = create_app()
    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready/config")
    assert health.status_code == 200
    assert ready.status_code == 503
    body = ready.json()
    assert body["ok"] is False
    assert body["ready"] is False
    assert body["dependencies_checked"] is False
    assert redis_inits["n"] == 0
    assert get_redis() is None


def test_invalid_production_does_not_start_operational(monkeypatch: pytest.MonkeyPatch) -> None:
    redis_inits = {"n": 0}

    async def _init(_settings=None):
        redis_inits["n"] += 1
        raise AssertionError("Redis must not initialize when production config is invalid")

    monkeypatch.setattr("sdr.redis_client.init_redis", _init)
    _neutral_env(
        monkeypatch,
        SDR_ENVIRONMENT="production",
        SDR_OUTBOUND_POLICY="deny_all",
        SDR_WEBHOOK_SECRET="not-a-placeholder",
        SDR_DOCUMENTS_BUCKET="sdr-documents-test",
    )
    app = create_app()
    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready/config")
    assert health.status_code == 200
    assert ready.status_code == 503
    assert ready.json()["ready"] is False
    assert redis_inits["n"] == 0
