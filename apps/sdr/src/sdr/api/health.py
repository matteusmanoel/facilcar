"""Health and config-readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sdr.config import get_settings
from sdr.domain.runtime_settings import RuntimeConfigError, validate_runtime_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, bool]:
    settings = getattr(request.app.state, "settings", None) or get_settings()
    return {"ok": True, "julia_enabled": bool(settings.julia_enabled)}


@router.get("/ready/config", response_model=None)
async def ready_config(request: Request):
    settings = getattr(request.app.state, "settings", None) or get_settings()
    try:
        report = validate_runtime_settings(settings)
    except RuntimeConfigError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "ready": False,
                "error": str(exc),
                "dependencies_checked": False,
            },
        )
    return {
        "ok": True,
        "ready": report.ready,
        "environment": report.environment,
        "outbound_policy": report.outbound_policy,
        "dependencies_checked": False,
    }
