"""Deterministic phone allowlist / deny-by-default for SDR inbound and outbound."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sdr.domain.phone import normalize_phone

VALID_ENVIRONMENTS = frozenset({"sandbox", "staging", "production"})
VALID_POLICIES = frozenset({"deny_all", "allowlist", "unrestricted"})


class OutboundDeniedError(Exception):
    """Raised when an outbound Evolution call is blocked before HTTP."""

    def __init__(self, *, phone: str, reason: str) -> None:
        self.reason = reason
        self.masked_phone = mask_phone(phone)
        super().__init__(f"outbound denied ({reason}) for {self.masked_phone}")


@dataclass(frozen=True, slots=True)
class PhoneAccessDecision:
    allowed: bool
    reason: str
    detail: str = ""


def parse_allowlist(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    seen: list[str] = []
    for part in str(raw).replace("\n", ",").split(","):
        digits = normalize_phone(part)
        if digits and digits not in seen:
            seen.append(digits)
    return tuple(seen)


def mask_phone(raw: str | None) -> str:
    digits = normalize_phone(raw)
    if not digits:
        return "****"
    if len(digits) <= 4:
        return "*" * len(digits)
    return ("*" * (len(digits) - 4)) + digits[-4:]


def evaluate_phone_access(
    phone: str,
    *,
    environment: str,
    policy: str,
    allowlist: Iterable[str],
) -> PhoneAccessDecision:
    env = (environment or "").strip().lower()
    pol = (policy or "").strip().lower()
    listed = tuple(normalize_phone(item) for item in allowlist)
    listed = tuple(item for item in listed if item)
    target = normalize_phone(phone)
    if env not in VALID_ENVIRONMENTS:
        return PhoneAccessDecision(allowed=False, reason="invalid_environment")
    if pol not in VALID_POLICIES:
        return PhoneAccessDecision(allowed=False, reason="invalid_policy")
    if not target:
        return PhoneAccessDecision(allowed=False, reason="missing_phone")
    if pol == "deny_all":
        return PhoneAccessDecision(allowed=False, reason="deny_all")
    if pol == "unrestricted":
        if env != "production":
            return PhoneAccessDecision(
                allowed=False, reason="unrestricted_requires_production"
            )
        return PhoneAccessDecision(allowed=True, reason="unrestricted")
    if target in listed:
        return PhoneAccessDecision(allowed=True, reason="allowlisted")
    return PhoneAccessDecision(allowed=False, reason="not_in_allowlist")


FOLLOWUP_PHONE_CANCEL = "PHONE_NOT_ALLOWED"
FOLLOWUP_PHONE_RETRY = "PHONE_ACCESS_UNAVAILABLE"


def classify_followup_phone_block(
    phone: str,
    *,
    environment: str,
    policy: str,
    allowlist: Iterable[str],
) -> str | None:
    """Permanent cancel only for a proven allowlist miss. Everything else is retryable."""
    try:
        listed = tuple(item for item in (normalize_phone(item) for item in allowlist) if item)
        decision = evaluate_phone_access(
            phone,
            environment=environment,
            policy=policy,
            allowlist=listed,
        )
    except Exception:
        return FOLLOWUP_PHONE_RETRY
    if decision.allowed:
        return None
    env = (environment or "").strip().lower()
    pol = (policy or "").strip().lower()
    if (
        env in VALID_ENVIRONMENTS
        and pol == "allowlist"
        and listed
        and decision.reason == "not_in_allowlist"
    ):
        return FOLLOWUP_PHONE_CANCEL
    return FOLLOWUP_PHONE_RETRY


def ensure_outbound_allowed(phone: str, settings: Any) -> None:
    decision = evaluate_phone_access(
        phone,
        environment=str(getattr(settings, "sdr_environment", "") or ""),
        policy=str(getattr(settings, "sdr_outbound_policy", "") or ""),
        allowlist=parse_allowlist(getattr(settings, "sdr_outbound_allowlist", "") or ""),
    )
    if not decision.allowed:
        raise OutboundDeniedError(phone=phone, reason=decision.reason)
