"""Unit tests for asyncpg SSL decision."""

from __future__ import annotations

from sdr.db import _dsn_requires_ssl


def test_local_hosts_skip_ssl() -> None:
    assert _dsn_requires_ssl("postgresql://postgres:postgres@localhost:5432/facilcar") is False
    assert _dsn_requires_ssl("postgresql://postgres:postgres@127.0.0.1:5432/facilcar") is False
    assert (
        _dsn_requires_ssl(
            "postgresql://postgres:postgres@host.docker.internal:5432/facilcar"
        )
        is False
    )


def test_supabase_pooler_requires_ssl() -> None:
    assert (
        _dsn_requires_ssl(
            "postgresql://postgres.ref:pw@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
        )
        is True
    )


def test_explicit_sslmode_disable() -> None:
    assert (
        _dsn_requires_ssl(
            "postgresql://u:p@db.example.com:5432/postgres?sslmode=disable"
        )
        is False
    )


def test_explicit_sslmode_require() -> None:
    assert (
        _dsn_requires_ssl(
            "postgresql://u:p@localhost:5432/facilcar?sslmode=require"
        )
        is True
    )
