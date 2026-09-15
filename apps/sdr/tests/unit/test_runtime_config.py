"""Phase 13A — deterministic config validation. No network."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sdr.config import Settings, get_settings
from sdr.domain.runtime_settings import (
    PLACEHOLDER_WEBHOOK_SECRETS,
    RuntimeConfigError,
    validate_runtime_settings,
)
from sdr.main import create_app


def _settings(**overrides: object) -> Settings:
    data: dict[str, object] = {
        "database_url": "postgresql://unused:unused@localhost:5432/unused",
        "redis_url": "redis://localhost:6379/15",
        "sdr_webhook_secret": "test-sdr-secret",
        "sdr_environment": "sandbox",
        "sdr_outbound_policy": "deny_all",
        "sdr_outbound_allowlist": "",
        "sdr_documents_bucket": "",
        "storage_endpoint": "",
        "storage_access_key": "",
        "storage_secret_key": "",
    }
    data.update(overrides)
    return Settings(**data)


def test_sandbox_defaults_are_valid_and_deny_outbound() -> None:
    settings = _settings()
    report = validate_runtime_settings(settings)
    assert report.environment == "sandbox"
    assert report.outbound_policy == "deny_all"
    assert report.ready is True


def test_staging_placeholder_webhook_secret_is_rejected() -> None:
    for secret in PLACEHOLDER_WEBHOOK_SECRETS:
        with pytest.raises(RuntimeConfigError, match="webhook"):
            validate_runtime_settings(
                _settings(
                    sdr_environment="staging",
                    sdr_outbound_policy="allowlist",
                    sdr_outbound_allowlist="5511999000101",
                    sdr_webhook_secret=secret,
                    sdr_documents_bucket="sdr-documents-test",
                )
            )


def test_staging_requires_explicit_documents_bucket() -> None:
    with pytest.raises(RuntimeConfigError, match="documents"):
        validate_runtime_settings(
            _settings(
                sdr_environment="staging",
                sdr_outbound_policy="allowlist",
                sdr_outbound_allowlist="5511999000101",
                sdr_webhook_secret="not-a-placeholder",
                sdr_documents_bucket="",
            )
        )


def test_vehicle_images_bucket_rejected_in_validation() -> None:
    with pytest.raises(RuntimeConfigError, match="vehicle-images"):
        validate_runtime_settings(
            _settings(
                sdr_environment="staging",
                sdr_outbound_policy="allowlist",
                sdr_outbound_allowlist="5511999000101",
                sdr_webhook_secret="not-a-placeholder",
                sdr_documents_bucket="vehicle-images",
            )
        )


def test_storage_enabled_without_bucket_fails() -> None:
    with pytest.raises(RuntimeConfigError, match="documents"):
        validate_runtime_settings(
            _settings(
                sdr_environment="sandbox",
                storage_endpoint="http://127.0.0.1:9000",
                storage_access_key="ak",
                storage_secret_key="sk",
                sdr_documents_bucket="",
            )
        )


def test_validation_error_does_not_include_secrets() -> None:
    try:
        validate_runtime_settings(
            _settings(
                sdr_environment="staging",
                sdr_outbound_policy="allowlist",
                sdr_outbound_allowlist="5511999000101",
                sdr_webhook_secret="super-secret-value-xyz",
                sdr_documents_bucket="vehicle-images",
            )
        )
    except RuntimeConfigError as exc:
        assert "super-secret-value-xyz" not in str(exc)
        assert "ak" not in str(exc) or "documents" in str(exc)
    else:
        raise AssertionError("expected RuntimeConfigError")


def test_health_is_not_config_readiness() -> None:
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        body = health.json()
        assert body.get("ok") is True
        assert "postgres" not in body
        assert "evolution" not in body
        assert "redis" not in body
        assert "storage" not in body
        ready = client.get("/ready/config")
        assert ready.status_code in {200, 503}
        payload = ready.json()
        assert payload.get("dependencies_checked") is False
        assert "evolution_healthy" not in payload
        assert "postgres_healthy" not in payload
