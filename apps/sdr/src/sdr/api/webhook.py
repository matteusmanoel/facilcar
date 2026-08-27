"""Evolution webhook ingress + debounce activity bump."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from sdr.config import Settings, get_settings
from sdr.debounce import mark_activity
from sdr.domain.phone import normalize_phone
from sdr.redis_client import get_redis

router = APIRouter(tags=["webhook"])


class WebhookAck(BaseModel):
    ok: bool = True
    accepted: bool = True
    julia_enabled: bool
    processed: bool = False
    message: str
    debounce_marked: bool = False


class DebounceMarkRequest(BaseModel):
    phone: str = Field(min_length=1)


class DebounceMarkResponse(BaseModel):
    ok: bool = True
    phone: str
    marked: bool


def _extract_secret(
    x_sdr_secret: str | None,
    authorization: str | None,
) -> str | None:
    if x_sdr_secret and x_sdr_secret.strip():
        return x_sdr_secret.strip()
    if authorization:
        value = authorization.strip()
        if value.lower().startswith("bearer "):
            token = value[7:].strip()
            return token or None
        return value or None
    return None


def _authorize(settings: Settings, provided: str | None) -> None:
    expected = (settings.sdr_webhook_secret or "").strip()
    if not expected or not provided or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )


def _phones_from_payload(body: Any) -> list[str]:
    """Best-effort phone extraction from Evolution-like payloads."""
    phones: list[str] = []
    if not isinstance(body, dict):
        return phones

    def _add(raw: str | None) -> None:
        digits = normalize_phone(raw)
        if digits and digits not in phones:
            phones.append(digits)

    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if isinstance(data, dict):
        key = data.get("key") if isinstance(data.get("key"), dict) else {}
        _add(key.get("remoteJid"))
        _add(key.get("remoteJidAlt"))
        _add(data.get("remoteJid"))
    _add(body.get("phone"))
    return phones


@router.post("/webhook/evolution", response_model=WebhookAck)
async def evolution_webhook(
    request: Request,
    x_sdr_secret: str | None = Header(default=None, alias="x-sdr-secret"),
    authorization: str | None = Header(default=None),
) -> WebhookAck:
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    _authorize(settings, _extract_secret(x_sdr_secret, authorization))

    body: Any = None
    try:
        body = await request.json()
    except Exception:
        body = None

    debounce_marked = False
    client = get_redis()
    if client is not None:
        for phone in _phones_from_payload(body):
            try:
                await mark_activity(client, phone, settings=settings)
                debounce_marked = True
            except Exception:
                pass

    julia_on = bool(settings.julia_enabled)
    if not julia_on:
        return WebhookAck(
            ok=True,
            accepted=True,
            julia_enabled=False,
            processed=False,
            debounce_marked=debounce_marked,
            message="accepted (julia disabled)",
        )

    return WebhookAck(
        ok=True,
        accepted=True,
        julia_enabled=True,
        processed=False,
        debounce_marked=debounce_marked,
        message="accepted (debounce marked; AI via worker poll)",
    )


@router.post("/internal/debounce", response_model=DebounceMarkResponse)
async def mark_debounce_activity(
    payload: DebounceMarkRequest,
    request: Request,
    x_sdr_secret: str | None = Header(default=None, alias="x-sdr-secret"),
    authorization: str | None = Header(default=None),
) -> DebounceMarkResponse:
    """Explicit quiet-window bump from Next.js ingest (Redis only)."""
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    _authorize(settings, _extract_secret(x_sdr_secret, authorization))
    phone = normalize_phone(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="invalid_phone")
    client = get_redis()
    marked = False
    if client is not None:
        await mark_activity(client, phone, settings=settings)
        marked = True
    return DebounceMarkResponse(ok=True, phone=phone, marked=marked)
