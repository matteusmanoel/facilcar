"""Customer upsert by normalized phone (asyncpg)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import asyncpg

from sdr.domain.phone import normalize_phone

SCHEMA = "facilcar"


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    # Naive UTC — asyncpg + Supabase timestamptz (Python 3.14 compat)
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CustomerRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_by_phone(self, phone: str) -> asyncpg.Record | None:
        digits = normalize_phone(phone)
        sql = f'''
            SELECT * FROM "{SCHEMA}"."Customer"
            WHERE "phone" = $1
            LIMIT 1
        '''
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(sql, digits)

    async def upsert_by_phone(
        self,
        phone: str,
        *,
        name: str | None = None,
        email: str | None = None,
    ) -> asyncpg.Record:
        """Upsert Customer keyed by digits-only phone (matches web resolveCustomerForLead)."""
        digits = normalize_phone(phone)
        if not digits:
            raise ValueError("phone is required")

        existing = await self.find_by_phone(digits)
        now = _now()
        display_name = (name or "").strip() or f"WhatsApp {digits[-4:]}"

        if existing:
            # Do not overwrite a real name with placeholder; update when provided.
            sql = f'''
                UPDATE "{SCHEMA}"."Customer"
                SET "name" = CASE
                        WHEN $2 <> '' AND ($2 NOT LIKE 'WhatsApp %') THEN $2
                        ELSE "name"
                    END,
                    "email" = COALESCE($3, "email"),
                    "updatedAt" = $4
                WHERE "id" = $1
                RETURNING *
            '''
            async with self._pool.acquire() as conn:
                return await conn.fetchrow(
                    sql,
                    existing["id"],
                    (name or "").strip(),
                    email,
                    now,
                )

        cid = _new_id()
        sql = f'''
            INSERT INTO "{SCHEMA}"."Customer"
              ("id", "name", "phone", "email", "createdAt", "updatedAt")
            VALUES ($1, $2, $3, $4, $5, $5)
            ON CONFLICT ("phone") DO UPDATE
              SET "updatedAt" = EXCLUDED."updatedAt"
            RETURNING *
        '''
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(sql, cid, display_name, digits, email, now)
