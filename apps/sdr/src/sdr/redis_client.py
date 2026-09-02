"""Redis client stub for locks / debounce (Wave 1+)."""

from __future__ import annotations

from typing import Optional

import redis.asyncio as redis

from sdr.config import Settings, get_settings

_client: Optional[redis.Redis] = None


async def init_redis(settings: Settings | None = None) -> redis.Redis:
    global _client
    if _client is not None:
        return _client
    cfg = settings or get_settings()
    _client = redis.from_url(cfg.redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_redis() -> Optional[redis.Redis]:
    return _client
