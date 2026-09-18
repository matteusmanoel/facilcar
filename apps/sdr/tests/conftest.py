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
# Pytest never calls the live LLM — `python -m sdr.replay --llm-real` does.
os.environ["OPENAI_API_KEY"] = ""
os.environ.setdefault("SDR_ENVIRONMENT", "sandbox")
os.environ.setdefault("SDR_OUTBOUND_POLICY", "allowlist")
# Synthetic fixture numbers only. The Phase 13A denied number is intentionally absent.
os.environ.setdefault(
    "SDR_OUTBOUND_ALLOWLIST",
    ",".join(
        [
            "5511999000101",
            "5511999999999",
            "554588230845",
            "5541999999999",
            "5511988001100",
            "5511900000001",
            "5511900000002",
            "5545999999999",
            "5511999990000",
            "5511999990001",
            "5511999990007",
            "5511999990009",
            "5511999000200",
            "5511999000001",
            "5545988432998",
            "5511999000099",
            "5511999000100",
            "5511988002200",
            "5511988887777",
            "5511888777666",
            "5545999000000",
            *[f"55119990000{i:02d}" for i in range(11, 21)],
        ]
    ),
)


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
