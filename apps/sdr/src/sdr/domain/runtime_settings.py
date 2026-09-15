"""Fail-closed runtime config validation. No network and no secret echoing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sdr.domain.document_storage import FORBIDDEN_DOCUMENT_BUCKETS
from sdr.domain.phone_access import VALID_ENVIRONMENTS, VALID_POLICIES, parse_allowlist

PLACEHOLDER_WEBHOOK_SECRETS = frozenset(
    {
        "",
        "change-me-local-secret",
        "changeme",
        "secret",
        "password",
        "webhook-secret",
    }
)


class RuntimeConfigError(ValueError):
    """Configuration is not safe to run."""


@dataclass(frozen=True, slots=True)
class RuntimeConfigReport:
    ready: bool
    environment: str
    outbound_policy: str


def _storage_enabled(settings: Any) -> bool:
    return bool(
        str(getattr(settings, "storage_endpoint", "") or "").strip()
        and str(getattr(settings, "storage_access_key", "") or "").strip()
        and str(getattr(settings, "storage_secret_key", "") or "").strip()
    )


def _require_private_documents_bucket(bucket: str, *, context: str) -> None:
    if not bucket:
        raise RuntimeConfigError(f"documents bucket is required {context}")
    if bucket in FORBIDDEN_DOCUMENT_BUCKETS:
        raise RuntimeConfigError("documents bucket cannot be vehicle-images")


def validate_runtime_settings(settings: Any) -> RuntimeConfigReport:
    env = str(getattr(settings, "sdr_environment", "") or "").strip().lower()
    policy = str(getattr(settings, "sdr_outbound_policy", "deny_all") or "deny_all")
    policy = policy.strip().lower()
    allowlist = parse_allowlist(getattr(settings, "sdr_outbound_allowlist", "") or "")
    bucket = str(getattr(settings, "sdr_documents_bucket", "") or "").strip()
    secret = str(getattr(settings, "sdr_webhook_secret", "") or "").strip()

    if env not in VALID_ENVIRONMENTS:
        raise RuntimeConfigError("invalid SDR_ENVIRONMENT")
    if policy not in VALID_POLICIES:
        raise RuntimeConfigError("invalid SDR_OUTBOUND_POLICY")
    if policy == "unrestricted" and env != "production":
        raise RuntimeConfigError("unrestricted outbound is only valid in production")

    if env == "staging":
        if policy != "allowlist":
            raise RuntimeConfigError("staging requires outbound allowlist policy")
        if not allowlist:
            raise RuntimeConfigError("staging allowlist is empty")
        if secret in PLACEHOLDER_WEBHOOK_SECRETS:
            raise RuntimeConfigError("webhook secret is a placeholder")
        _require_private_documents_bucket(bucket, context="for staging")

    if env == "production":
        if policy == "deny_all":
            raise RuntimeConfigError("production requires an explicit outbound policy")
        if policy == "allowlist" and not allowlist:
            raise RuntimeConfigError("production allowlist is empty")
        if secret in PLACEHOLDER_WEBHOOK_SECRETS:
            raise RuntimeConfigError("webhook secret is a placeholder")
        _require_private_documents_bucket(bucket, context="for production")

    if _storage_enabled(settings):
        _require_private_documents_bucket(bucket, context="when storage is enabled")

    return RuntimeConfigReport(ready=True, environment=env, outbound_policy=policy)
