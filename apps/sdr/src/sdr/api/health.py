"""Health endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from sdr.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, bool]:
    settings = getattr(request.app.state, "settings", None) or get_settings()
    return {"ok": True, "julia_enabled": bool(settings.julia_enabled)}
