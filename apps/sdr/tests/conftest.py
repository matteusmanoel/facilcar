"""Pytest fixtures — no live DB/Redis required for Wave 0 unit tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Ensure deterministic settings before app import / factory.
os.environ.setdefault("SDR_WEBHOOK_SECRET", "test-sdr-secret")
os.environ.setdefault("JULIA_ENABLED", "false")
os.environ.setdefault("SDR_TRANSPORT_MODE", "vercel_relay")
os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@localhost:5432/unused")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")


@pytest.fixture
def webhook_secret() -> str:
    return os.environ["SDR_WEBHOOK_SECRET"]


@pytest.fixture
def client(webhook_secret: str) -> TestClient:
    from sdr.config import get_settings
    from sdr.main import create_app

    get_settings.cache_clear()
    os.environ["SDR_WEBHOOK_SECRET"] = webhook_secret
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
