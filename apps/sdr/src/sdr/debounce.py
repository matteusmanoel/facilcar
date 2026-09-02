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


def dynamic_debounce_ms(
    assistant_turn_count: int,
    *,
    base_ms: int | None = None,
    settings: Settings | None = None,
) -> int:
    """Shorter coalesce on first contact; more typing room after Júlia has spoken."""
    cfg = settings or get_settings()
    base = int(base_ms if base_ms is not None else cfg.sdr_debounce_ms)
    count = max(0, int(assistant_turn_count or 0))
    if count <= 0:
        return max(800, min(base, 1200))
    return min(4500, 2000 + min(count, 8) * 300)


async def wait_until_quiet(
    client: redis.Redis | None,
    phone: str,
    *,
    debounce_ms: int | None = None,
    settings: Settings | None = None,
    max_extensions: int = 20,
    assistant_turn_count: int | None = None,
) -> None:
    """Block until the phone has been quiet for ``debounce_ms``.

    With Redis: loop while ``mark_activity`` refreshes the key (new inbound).
    Without Redis: single sleep (cannot observe mid-wait arrivals).
    """
    cfg = settings or get_settings()
    if debounce_ms is not None:
        window_ms = debounce_ms
    elif assistant_turn_count is not None:
        window_ms = dynamic_debounce_ms(assistant_turn_count, settings=cfg)
    else:
        window_ms = cfg.sdr_debounce_ms
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
