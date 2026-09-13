"""Debounce window before processing a burst of inbound messages.

Redis holds only ephemeral activity markers. Official batch composition lives
in Postgres. Waiting is purely temporal per phone — no content heuristics.

The quiet window is the same on first contact and later turns. A hard max wait
from wait-start prevents a sliding window from running forever.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import redis.asyncio as redis

from sdr.config import Settings, get_settings

DEBOUNCE_KEY_PREFIX = "sdr:debounce:phone:"

QuietCloseReason = Literal["quiet", "max_wait", "max_extensions"]


class QuietClock(Protocol):
    def monotonic(self) -> float: ...
    def time_ns(self) -> int: ...
    async def sleep(self, seconds: float) -> None: ...


class _SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def time_ns(self) -> int:
        return time.time_ns()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


@dataclass(slots=True)
class QuietWindowResult:
    close_reason: QuietCloseReason
    window_ms: int
    waited_ms: int
    extensions: int


def quiet_window_ms(
    *,
    base_ms: int | None = None,
    settings: Settings | None = None,
) -> int:
    """Configured quiet window. Independent of assistant_turn_count."""
    cfg = settings or get_settings()
    return int(base_ms if base_ms is not None else cfg.sdr_debounce_ms)


def debounce_max_ms(*, settings: Settings | None = None) -> int:
    cfg = settings or get_settings()
    return max(int(cfg.sdr_debounce_max_ms), quiet_window_ms(settings=cfg))


def dynamic_debounce_ms(
    assistant_turn_count: int,
    *,
    base_ms: int | None = None,
    settings: Settings | None = None,
) -> int:
    """Quiet window is identical on first contact and later turns.

    ``assistant_turn_count`` is accepted for call-site compatibility and ignored.
    A shorter first-contact window split real 6s bursts into two decisions.
    """
    _ = assistant_turn_count
    return quiet_window_ms(base_ms=base_ms, settings=settings)


def _result(
    *,
    reason: QuietCloseReason,
    window_ms: int,
    start: float,
    clock: QuietClock,
    extensions: int,
) -> QuietWindowResult:
    waited_ms = max(0, int((clock.monotonic() - start) * 1000))
    return QuietWindowResult(
        close_reason=reason,
        window_ms=window_ms,
        waited_ms=waited_ms,
        extensions=extensions,
    )


async def wait_until_quiet(
    client: redis.Redis | None,
    phone: str,
    *,
    debounce_ms: int | None = None,
    settings: Settings | None = None,
    max_extensions: int = 20,
    assistant_turn_count: int | None = None,
    clock: QuietClock | None = None,
    max_wait_ms: int | None = None,
) -> QuietWindowResult:
    """Block until the phone has been quiet for ``debounce_ms``.

    With Redis: loop while ``mark_activity`` refreshes the key (new inbound).
    Without Redis: single sleep (cannot observe mid-wait arrivals).
    Close reasons: ``quiet`` | ``max_wait`` | ``max_extensions``.
    """
    _ = assistant_turn_count
    cfg = settings or get_settings()
    window_ms = int(debounce_ms if debounce_ms is not None else quiet_window_ms(settings=cfg))
    cap_ms = int(max_wait_ms if max_wait_ms is not None else debounce_max_ms(settings=cfg))
    ticker: QuietClock = clock or _SystemClock()
    start = ticker.monotonic()

    if window_ms <= 0:
        return _result(
            reason="quiet", window_ms=window_ms, start=start, clock=ticker, extensions=0
        )

    if client is None:
        sleep_s = min(window_ms, cap_ms) / 1000.0
        await ticker.sleep(max(sleep_s, 0.0))
        reason: QuietCloseReason = "max_wait" if window_ms >= cap_ms and cap_ms <= window_ms else "quiet"
        if int((ticker.monotonic() - start) * 1000) >= cap_ms and window_ms >= cap_ms:
            reason = "max_wait"
        return _result(
            reason=reason, window_ms=window_ms, start=start, clock=ticker, extensions=0
        )

    key = f"{DEBOUNCE_KEY_PREFIX}{phone}"
    extensions = 0
    while True:
        elapsed_ms = (ticker.monotonic() - start) * 1000.0
        remaining_ms = cap_ms - elapsed_ms
        if remaining_ms <= 0:
            return _result(
                reason="max_wait",
                window_ms=window_ms,
                start=start,
                clock=ticker,
                extensions=extensions,
            )
        token = str(ticker.time_ns())
        ttl = max(int((window_ms / 1000.0) * 3) or 1, 5)
        await client.set(key, token, ex=ttl)
        await ticker.sleep(min(window_ms, remaining_ms) / 1000.0)
        if (ticker.monotonic() - start) * 1000.0 >= cap_ms:
            return _result(
                reason="max_wait",
                window_ms=window_ms,
                start=start,
                clock=ticker,
                extensions=extensions,
            )
        current: Any = await client.get(key)
        if current is None or current == token:
            return _result(
                reason="quiet",
                window_ms=window_ms,
                start=start,
                clock=ticker,
                extensions=extensions,
            )
        extensions += 1
        if extensions >= max_extensions:
            return _result(
                reason="max_extensions",
                window_ms=window_ms,
                start=start,
                clock=ticker,
                extensions=extensions,
            )


async def wait_debounce(
    client: redis.Redis | None,
    phone: str,
    *,
    debounce_ms: int | None = None,
    settings: Settings | None = None,
) -> QuietWindowResult:
    """Backward-compatible alias → :func:`wait_until_quiet`."""
    return await wait_until_quiet(
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
    ttl = max(int((quiet_window_ms(settings=cfg) / 1000.0) * 3) or 1, 5)
    await client.set(f"{DEBOUNCE_KEY_PREFIX}{phone}", str(time.time_ns()), ex=ttl)
