"""SdrDocument persistence (asyncpg) + retention policy helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import asyncpg

SCHEMA = "facilcar"

RETENTION_DAYS_180 = "DAYS_180"
RETENTION_PERMANENT = "PERMANENT"
DEFAULT_RETENTION_DAYS = 180


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def retention_policy_for_lead_status(lead_status: str | None) -> str:
    """DAYS_180 by default; PERMANENT when lead is WON."""
    if lead_status and str(lead_status).strip().upper() == "WON":
        return RETENTION_PERMANENT
    return RETENTION_DAYS_180


def expires_at_for_policy(
    policy: str,
    *,
    created_at: datetime | None = None,
) -> datetime | None:
    """PERMANENT → no expiry; DAYS_180 → created_at + 180 days."""
    if policy == RETENTION_PERMANENT:
        return None
    base = created_at or _now()
    return base + timedelta(days=DEFAULT_RETENTION_DAYS)


class DocumentRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(
        self,
        *,
        storage_key: str,
        document_type: str = "OTHER",
        lead_id: str | None = None,
        conversation_id: str | None = None,
        mime_type: str | None = None,
        byte_size: int | None = None,
        extracted_json: Mapping[str, Any] | None = None,
        extraction_status: str = "PENDING",
        retention_policy: str | None = None,
        lead_status: str | None = None,
        expires_at: datetime | None = None,
    ) -> asyncpg.Record:
        """Insert into facilcar.\"SdrDocument\" (default retention DAYS_180)."""
        policy = retention_policy or retention_policy_for_lead_status(lead_status)
        created = _now()
        exp = expires_at
        if exp is None and policy != RETENTION_PERMANENT:
            exp = expires_at_for_policy(policy, created_at=created)

        doc_type = (document_type or "OTHER").upper()
        status = (extraction_status or "PENDING").upper()
        payload = json.dumps(dict(extracted_json), ensure_ascii=False) if extracted_json else None
        doc_id = _new_id()

        sql = f'''
            INSERT INTO "{SCHEMA}"."SdrDocument"
              ("id", "leadId", "conversationId", "documentType", "storageKey",
               "mimeType", "byteSize", "extractedJson", "extractionStatus",
               "retentionPolicy", "expiresAt", "createdAt")
            VALUES (
              $1, $2, $3,
              $4::"{SCHEMA}"."SdrDocumentType",
              $5, $6, $7,
              $8::jsonb,
              $9::"{SCHEMA}"."SdrDocumentExtractionStatus",
              $10::"{SCHEMA}"."SdrRetentionPolicy",
              $11, $12
            )
            RETURNING *
        '''
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                sql,
                doc_id,
                lead_id,
                conversation_id,
                doc_type,
                storage_key,
                mime_type,
                byte_size,
                payload,
                status,
                policy,
                exp,
                created,
            )

    async def mark_permanent_for_won_lead(self, lead_id: str) -> int:
        """When lead is WON: set retentionPolicy=PERMANENT and clear expiresAt."""
        sql = f'''
            UPDATE "{SCHEMA}"."SdrDocument"
            SET "retentionPolicy" = 'PERMANENT'::"{SCHEMA}"."SdrRetentionPolicy",
                "expiresAt" = NULL
            WHERE "leadId" = $1
              AND "retentionPolicy" <> 'PERMANENT'::"{SCHEMA}"."SdrRetentionPolicy"
        '''
        async with self._pool.acquire() as conn:
            status = await conn.execute(sql, lead_id)
        # asyncpg returns e.g. "UPDATE 3"
        try:
            return int(str(status).split()[-1])
        except (ValueError, IndexError):
            return 0

    async def update_extraction(
        self,
        document_id: str,
        *,
        extracted_json: Mapping[str, Any] | None,
        extraction_status: str = "DONE",
        document_type: str | None = None,
    ) -> asyncpg.Record | None:
        status = extraction_status.upper()
        payload = (
            json.dumps(dict(extracted_json), ensure_ascii=False)
            if extracted_json is not None
            else None
        )
        if document_type:
            sql = f'''
                UPDATE "{SCHEMA}"."SdrDocument"
                SET "extractedJson" = $2::jsonb,
                    "extractionStatus" = $3::"{SCHEMA}"."SdrDocumentExtractionStatus",
                    "documentType" = $4::"{SCHEMA}"."SdrDocumentType"
                WHERE "id" = $1
                RETURNING *
            '''
            args: tuple[Any, ...] = (
                document_id,
                payload,
                status,
                document_type.upper(),
            )
        else:
            sql = f'''
                UPDATE "{SCHEMA}"."SdrDocument"
                SET "extractedJson" = $2::jsonb,
                    "extractionStatus" = $3::"{SCHEMA}"."SdrDocumentExtractionStatus"
                WHERE "id" = $1
                RETURNING *
            '''
            args = (document_id, payload, status)

        async with self._pool.acquire() as conn:
            return await conn.fetchrow(sql, *args)
