"""FastAPI application factory for FacilCar SDR."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from sdr.api.health import router as health_router
from sdr.api.webhook import router as webhook_router
from sdr.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Connect Redis when available so /internal/debounce can bump quiet windows.
    # DB remains worker-owned for the MVP poll path.
    settings = get_settings()
    app.state.settings = settings
    try:
        from sdr.redis_client import init_redis, close_redis

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
