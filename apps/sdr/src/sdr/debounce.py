"""Debounce window before processing a burst of inbound messages.

Redis holds only ephemeral activity markers. Official batch composition lives
in Postgres. Waiting is purely temporal per phone — no content heuristics.
"""

from __future__ import annotations

import asyncio
import time

import redis.asyncio as redis

from sdr.config import Settings, get_settings

DEBOUNCE_KEY_PREFIX = "sdr:debounce:phone:"


async def wait_until_quiet(
    client: redis.Redis | None,
    phone: str,
    *,
    debounce_ms: int | None = None,
    settings: Settings | None = None,
    max_extensions: int = 20,
) -> None:
    """Block until the phone has been quiet for ``debounce_ms``.

    With Redis: loop while ``mark_activity`` refreshes the key (new inbound).
    Without Redis: single sleep (cannot observe mid-wait arrivals).
    """
    cfg = settings or get_settings()
    window_ms = debounce_ms if debounce_ms is not None else cfg.sdr_debounce_ms
    window_s = max(window_ms, 0) / 1000.0
    if window_s <= 0:
        return

    if client is None:
        await asyncio.sleep(window_s)
        return

    key = f"{DEBOUNCE_KEY_PREFIX}{phone}"
    extensions = 0
    while True:
        token = str(time.time_ns())
        await client.set(key, token, ex=max(int(window_s * 3) or 1, 5))
        await asyncio.sleep(window_s)
        current = await client.get(key)
        if current is None or current == token:
            return
        extensions += 1
        if extensions >= max_extensions:
            return


async def wait_debounce(
    client: redis.Redis | None,
    phone: str,
    *,
    debounce_ms: int | None = None,
    settings: Settings | None = None,
) -> None:
    """Backward-compatible alias → :func:`wait_until_quiet`."""
    await wait_until_quiet(
        client, phone, debounce_ms=debounce_ms, settings=settings
    )


async def mark_activity(
    client: redis.Redis,
    phone: str,
    *,
    settings: Settings | None = None,
) -> None:
    """Bump debounce marker when a new inbound message arrives."""
    cfg = settings or get_settings()
    ttl = max(int((cfg.sdr_debounce_ms / 1000.0) * 3) or 1, 5)
    await client.set(f"{DEBOUNCE_KEY_PREFIX}{phone}", str(time.time_ns()), ex=ttl)
