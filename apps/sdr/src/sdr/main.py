"""FastAPI application factory for FacilCar SDR."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from sdr.api.health import router as health_router
from sdr.api.webhook import router as webhook_router
from sdr.config import get_settings
from sdr.domain.runtime_settings import RuntimeConfigError, validate_runtime_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Config validation is local (no network). Invalid staging/production must
    # not become operational; liveness stays up so operators can read /ready/config.
    settings = get_settings()
    app.state.settings = settings
    app.state.config_ready = False
    try:
        validate_runtime_settings(settings)
        app.state.config_ready = True
    except RuntimeConfigError as exc:
        logger.error("SDR runtime config is not ready: %s", exc)
    if app.state.config_ready:
        try:
            from sdr.redis_client import init_redis

            await init_redis(settings)
        except Exception:
            pass
    yield
    try:
        from sdr.redis_client import close_redis

        await close_redis()
    except Exception:
        pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="FacilCar SDR",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.julia_enabled = settings.julia_enabled
    app.state.settings = settings
    app.include_router(health_router)
    app.include_router(webhook_router)
    return app


app = create_app()
