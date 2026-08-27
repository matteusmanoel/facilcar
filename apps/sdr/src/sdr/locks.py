"""Redis lock per phone (conversation-level concurrency)."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as redis

from sdr.config import Settings, get_settings

LOCK_KEY_PREFIX = "sdr:lock:phone:"


class PhoneLock:
    """SET NX EX lock with token ownership for safe release."""

    def __init__(
        self,
        client: redis.Redis,
        phone: str,
        *,
        ttl_seconds: int | None = None,
        settings: Settings | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self._client = client
        self._phone = phone
        self._ttl = ttl_seconds if ttl_seconds is not None else cfg.sdr_lock_ttl_seconds
        self._key = f"{LOCK_KEY_PREFIX}{phone}"
        self._token = uuid.uuid4().hex
        self._held = False

    @property
    def key(self) -> str:
        return self._key

    async def acquire(self) -> bool:
        ok = await self._client.set(self._key, self._token, nx=True, ex=self._ttl)
        self._held = bool(ok)
        return self._held

    async def release(self) -> None:
        if not self._held:
            return
        # Release only if we still own the token.
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        await self._client.eval(script, 1, self._key, self._token)
        self._held = False

    async def __aenter__(self) -> PhoneLock:
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError(f"Could not acquire lock for phone={self._phone}")
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.release()


@asynccontextmanager
async def phone_lock(
    client: redis.Redis,
    phone: str,
    *,
    ttl_seconds: int | None = None,
    settings: Settings | None = None,
) -> AsyncIterator[PhoneLock]:
    lock = PhoneLock(client, phone, ttl_seconds=ttl_seconds, settings=settings)
    acquired = await lock.acquire()
    if not acquired:
        raise RuntimeError(f"Could not acquire lock for phone={phone}")
    try:
        yield lock
    finally:
        await lock.release()
