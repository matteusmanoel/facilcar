"""Test doubles for quiet-window and lock semantics — no live Redis/sleep."""

from __future__ import annotations

import heapq
from collections.abc import Awaitable, Callable
from typing import Any


class FakeClock:
    """Monotonic clock with scheduled callbacks during sleep (no wall wait)."""

    def __init__(self, start: float = 0.0) -> None:
        self.t = float(start)
        self.sleeps: list[float] = []
        self._events: list[tuple[float, int, Callable[[], Awaitable[None] | None]]] = []
        self._seq = 0

    def monotonic(self) -> float:
        return self.t

    def time_ns(self) -> int:
        return int(self.t * 1_000_000_000)

    def schedule(self, at: float, callback: Callable[[], Awaitable[None] | None]) -> None:
        self._seq += 1
        heapq.heappush(self._events, (float(at), self._seq, callback))

    async def sleep(self, seconds: float) -> None:
        seconds = max(0.0, float(seconds))
        self.sleeps.append(seconds)
        deadline = self.t + seconds
        while self._events and self._events[0][0] <= deadline:
            at, _seq, cb = heapq.heappop(self._events)
            self.t = at
            result = cb()
            if isinstance(result, Awaitable):
                await result
        self.t = deadline


class FakeRedis:
    """Minimal async Redis: GET/SET/NX/EX + token-compare DEL (lock Lua)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
        **_: Any,
    ) -> bool | None:
        _ = ex
        if nx and key in self.store:
            return False
        self.store[key] = str(value)
        return True

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, key: str) -> int:
        return 1 if self.store.pop(key, None) is not None else 0

    async def eval(self, script: str, numkeys: int, *args: str) -> int:
        _ = script
        key = args[0] if numkeys >= 1 else ""
        token = args[1] if len(args) > 1 else ""
        if self.store.get(key) == token:
            self.store.pop(key, None)
            return 1
        return 0
