"""Phase 13A — phone allowlist / deny-by-default. Synthetic numbers only."""

from __future__ import annotations

import pytest

from sdr.config import Settings
from sdr.domain.phone_access import (
    OutboundDeniedError,
    evaluate_phone_access,
    mask_phone,
    parse_allowlist,
)
from sdr.domain.runtime_settings import RuntimeConfigError, validate_runtime_settings

ALLOWED = "5511999000101"
DENIED = "5511999000199"


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


def test_staging_without_allowlist_fails_validation() -> None:
    with pytest.raises(RuntimeConfigError, match="allowlist"):
        validate_runtime_settings(_settings(sdr_environment="staging"))


def test_staging_with_empty_allowlist_fails_validation() -> None:
    with pytest.raises(RuntimeConfigError, match="allowlist"):
        validate_runtime_settings(
            _settings(
                sdr_environment="staging",
                sdr_outbound_policy="allowlist",
                sdr_outbound_allowlist="  ,  ",
            )
        )


def test_allowed_phone_passes_allowlist() -> None:
    decision = evaluate_phone_access(
        ALLOWED,
        environment="staging",
        policy="allowlist",
        allowlist=(ALLOWED,),
    )
    assert decision.allowed is True


def test_denied_phone_is_not_allowed() -> None:
    decision = evaluate_phone_access(
        DENIED,
        environment="staging",
        policy="allowlist",
        allowlist=(ALLOWED,),
    )
    assert decision.allowed is False
    assert DENIED not in decision.reason
    assert ALLOWED not in (decision.detail or "")


def test_equivalent_phone_formats_normalize() -> None:
    decision = evaluate_phone_access(
        "+55 11 99900-0101",
        environment="staging",
        policy="allowlist",
        allowlist=("5511999000101@s.whatsapp.net",),
    )
    assert decision.allowed is True
    assert parse_allowlist("5511999000101, 55 11 99900-0101") == ("5511999000101",)


def test_invalid_environment_or_policy_denies() -> None:
    bad_env = evaluate_phone_access(
        ALLOWED, environment="prod", policy="allowlist", allowlist=(ALLOWED,)
    )
    bad_policy = evaluate_phone_access(
        ALLOWED, environment="sandbox", policy="open", allowlist=(ALLOWED,)
    )
    assert bad_env.allowed is False
    assert bad_policy.allowed is False


def test_production_is_not_unrestricted_by_default() -> None:
    settings = _settings(sdr_environment="production")
    with pytest.raises(RuntimeConfigError):
        validate_runtime_settings(settings)
    decision = evaluate_phone_access(
        ALLOWED,
        environment="production",
        policy="deny_all",
        allowlist=(),
    )
    assert decision.allowed is False


def test_unrestricted_rejected_outside_explicit_production() -> None:
    with pytest.raises(RuntimeConfigError):
        validate_runtime_settings(
            _settings(sdr_environment="staging", sdr_outbound_policy="unrestricted")
        )
    with pytest.raises(RuntimeConfigError):
        validate_runtime_settings(
            _settings(sdr_environment="sandbox", sdr_outbound_policy="unrestricted")
        )
    validate_runtime_settings(
        _settings(
            sdr_environment="production",
            sdr_outbound_policy="unrestricted",
            sdr_webhook_secret="staging-not-a-placeholder-secret",
            sdr_documents_bucket="sdr-documents-test",
        )
    )


def test_mask_phone_hides_full_number() -> None:
    masked = mask_phone(ALLOWED)
    assert ALLOWED not in masked
    assert masked.endswith("0101")
    assert "*" in masked


def test_outbound_denied_error_omits_phone() -> None:
    err = OutboundDeniedError(phone=DENIED, reason="not_in_allowlist")
    text = str(err)
    assert DENIED not in text
    assert "0101" in text or "denied" in text.lower()
