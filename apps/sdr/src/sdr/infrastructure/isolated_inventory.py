"""Isolated inventory/DB adapter for replay and gates.

Implements the minimum asyncpg.Pool protocol (``acquire`` / fetch) without
opening a remote connection. Dummy ``object()`` pools are coerced here so
visual/inventory paths cannot raise ``AttributeError: acquire``.
"""

from __future__ import annotations

from typing import Any


class IsolatedConnection:
    """Connection stub returned by ``IsolatedInventoryAdapter.acquire()``."""

    async def __aenter__(self) -> IsolatedConnection:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def fetch(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    async def fetchrow(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def fetchval(self, *args: Any, **kwargs: Any) -> None:
        return None


class IsolatedInventoryAdapter:
    """Pool-compatible adapter. Never connects to Postgres or Supabase."""

    isolated = True

    def acquire(self) -> IsolatedConnection:
        return IsolatedConnection()

    async def fetch(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    async def fetchrow(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def fetchval(self, *args: Any, **kwargs: Any) -> None:
        return None


def pool_protocol_compatible(pool: Any) -> bool:
    return pool is not None and hasattr(pool, "acquire") and callable(pool.acquire)


def coerce_isolated_pool(pool: Any) -> Any:
    """Replace a dummy/non-protocol pool. ``None`` stays ``None`` (no lookup)."""
    if pool is None:
        return None
    if pool_protocol_compatible(pool):
        return pool
    return IsolatedInventoryAdapter()
