"""Async Postgres pool. Prisma owns migrations (ADR-003)."""

from __future__ import annotations

from typing import Optional
from urllib.parse import parse_qs, urlparse

import asyncpg

from sdr.config import Settings, get_settings

_pool: Optional[asyncpg.Pool] = None

# Hosts that never speak TLS (local Docker / loopback).
_LOCAL_SSL_SKIP_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "host.docker.internal",
        "facilcar-db",
        "postgres",
        "db",
    }
)


def _dsn_requires_ssl(dsn: str) -> bool:
    """Decide SSL for asyncpg.

    - Explicit ``sslmode=disable`` → no SSL.
    - Explicit ``sslmode=require|verify-*`` → SSL.
    - Local / docker-internal hosts → no SSL.
    - Remote (e.g. Supabase pooler) → require SSL.
    """
    parsed = urlparse(dsn)
    query = parse_qs(parsed.query or "")
    raw_mode = (query.get("sslmode") or query.get("ssl") or [None])[0]
    if raw_mode is not None:
        mode = str(raw_mode).strip().lower()
        if mode in ("disable", "false", "0", "off"):
            return False
        if mode in ("require", "verify-ca", "verify-full", "true", "1", "on"):
            return True
        # prefer / allow → fall through to host heuristic

    host = (parsed.hostname or "").strip().lower()
    if host in _LOCAL_SSL_SKIP_HOSTS or host.endswith(".local"):
        return False
    return True


async def init_pool(settings: Settings | None = None) -> asyncpg.Pool:
    """Create a shared asyncpg pool (lazy; not required for health/webhook auth)."""
    global _pool
    if _pool is not None:
        return _pool
    cfg = settings or get_settings()
    dsn = cfg.database_url
    pool_kwargs: dict = {
        "dsn": dsn,
        "min_size": 1,
        "max_size": 5,
        # Supabase pooler (pgbouncer) — prepared statements break without this.
        "statement_cache_size": 0,
    }
    if _dsn_requires_ssl(dsn):
        pool_kwargs["ssl"] = "require"
    _pool = await asyncpg.create_pool(**pool_kwargs)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> Optional[asyncpg.Pool]:
    return _pool
