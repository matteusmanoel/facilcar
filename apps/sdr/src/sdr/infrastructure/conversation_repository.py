"""Conversation + Message persistence (asyncpg, Prisma column names)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from sdr.domain.types import (
    Actionability,
    BusinessIntent,
    BusinessState,
    BusinessType,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
    LeadTemperature,
    LifecycleState,
    LifecycleStatus,
)
from sdr.domain.budget_status import BudgetStatus, parse_budget_status
from sdr.domain.pending_interaction import (
    AlternativeScope,
    PendingInteraction,
    parse_alternative_scope,
    parse_pending_interaction,
)
from sdr.domain.inbound_batch import BATCH_JSON_KEY, InboundBatch, BatchStatus, merge_turn_facts

SCHEMA = "facilcar"


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def canonical_state_to_json(state: ConversationCanonicalState) -> str:
    payload = {
        "thread_id": state.thread_id,
        "language": state.language,
        "intent": state.intent.value,
        "customer": {
            "phone": state.customer.phone,
            "name": state.customer.name,
            "name_confirmed": state.customer.name_confirmed,
        },
        "business": {
            "type": state.business.type.value,
            "actionability": state.business.actionability.value,
        },
        "lifecycle": {
            "status": state.lifecycle.status.value,
            "handoff_reason": state.lifecycle.handoff_reason,
        },
        "facts": state.facts,
        "signals": state.signals.as_dict(),
        "pending_confirmation": state.pending_confirmation,
        "temperature": state.temperature.value if state.temperature else None,
        "active_lead_ids": state.active_lead_ids,
        "assistant_turn_count": state.assistant_turn_count,
        "last_inventory_search_key": state.last_inventory_search_key,
        "last_inventory_outcome": state.last_inventory_outcome,
        "pending_interaction": state.pending_interaction.value,
        "alternative_scope": state.alternative_scope.value,
        "budget_status": state.budget_status.value,
        "last_shown_vehicle_ids": list(state.last_shown_vehicle_ids),
        "photo_request": bool(state.photo_request),
        "pending_question": state.pending_question,
        "engagement_low_streak": int(state.engagement_low_streak),
        "visit_invited": bool(state.visit_invited),
        "visit_preferred_time": state.visit_preferred_time,
        "documents_asked": bool(state.documents_asked),
        "installment_asked": bool(state.installment_asked),
        "installment_mismatch_offered": bool(state.installment_mismatch_offered),
        "installment_capacity": state.installment_capacity,
        "last_shown_price_cash": state.last_shown_price_cash,
    }
    return json.dumps(payload)


def canonical_state_from_json(
    raw: Any,
    *,
    thread_id: str,
    phone: str,
    bot_status: str | None = None,
    active_lead_ids: list[str] | None = None,
) -> ConversationCanonicalState:
    data: dict[str, Any]
    if raw is None:
        data = {}
    elif isinstance(raw, str):
        data = json.loads(raw) if raw else {}
    elif isinstance(raw, dict):
        data = raw
    else:
        # asyncpg may return JSONB as str/dict depending on codec
        data = dict(raw)

    customer_raw = data.get("customer") or {}
    business_raw = data.get("business") or {}
    lifecycle_raw = data.get("lifecycle") or {}
    signals_raw = data.get("signals") or {}

    status_value = lifecycle_raw.get("status") or bot_status or LifecycleStatus.BOT_ACTIVE.value
    try:
        status = LifecycleStatus(status_value)
    except ValueError:
        status = LifecycleStatus.BOT_ACTIVE

    intent_value = data.get("intent") or BusinessIntent.UNKNOWN.value
    try:
        intent = BusinessIntent(intent_value)
    except ValueError:
        intent = BusinessIntent.UNKNOWN

    try:
        btype = BusinessType(business_raw.get("type") or BusinessType.UNKNOWN.value)
    except ValueError:
        btype = BusinessType.UNKNOWN

    try:
        actionability = Actionability(
            business_raw.get("actionability") or Actionability.INSUFFICIENT.value
        )
    except ValueError:
        actionability = Actionability.INSUFFICIENT

    temp = data.get("temperature")
    temperature = None
    if temp:
        try:
            temperature = LeadTemperature(temp)
        except ValueError:
            temperature = None

    return ConversationCanonicalState(
        thread_id=data.get("thread_id") or thread_id,
        language=data.get("language") or "unknown",
        intent=intent,
        customer=CustomerState(
            phone=customer_raw.get("phone") or phone,
            name=customer_raw.get("name"),
            name_confirmed=bool(customer_raw.get("name_confirmed") or False),
        ),
        business=BusinessState(type=btype, actionability=actionability),
        lifecycle=LifecycleState(
            status=status,
            handoff_reason=lifecycle_raw.get("handoff_reason"),
        ),
        facts=dict(data.get("facts") or {}),
        signals=HandoffSignals(
            explicit_handoff=signals_raw.get("explicit_handoff"),
            explicit_offer=signals_raw.get("explicit_offer"),
            visit_intent=signals_raw.get("visit_intent"),
            high_purchase_intent=signals_raw.get("high_purchase_intent"),
            sensitive_data_refusal=signals_raw.get("sensitive_data_refusal"),
        ),
        pending_confirmation=list(data.get("pending_confirmation") or []),
        temperature=temperature,
        active_lead_ids=list(active_lead_ids or data.get("active_lead_ids") or []),
        assistant_turn_count=int(data.get("assistant_turn_count") or 0),
        last_inventory_search_key=data.get("last_inventory_search_key") or None,
        last_inventory_outcome=data.get("last_inventory_outcome") or None,
        pending_interaction=parse_pending_interaction(data.get("pending_interaction")),
        alternative_scope=parse_alternative_scope(data.get("alternative_scope"))
        or AlternativeScope.NONE,
        budget_status=parse_budget_status(data.get("budget_status")) or BudgetStatus.UNKNOWN,
        last_shown_vehicle_ids=[
            str(v) for v in (data.get("last_shown_vehicle_ids") or []) if v
        ],
        photo_request=bool(data.get("photo_request") or False),
        pending_question=data.get("pending_question") or None,
        engagement_low_streak=int(data.get("engagement_low_streak") or 0),
        visit_invited=bool(data.get("visit_invited") or False),
        visit_preferred_time=data.get("visit_preferred_time") or None,
        documents_asked=bool(data.get("documents_asked") or False),
        installment_asked=bool(data.get("installment_asked") or False),
        installment_mismatch_offered=bool(data.get("installment_mismatch_offered") or False),
        installment_capacity=(
            float(data["installment_capacity"])
            if data.get("installment_capacity") is not None
            else None
        ),
        last_shown_price_cash=(
            float(data["last_shown_price_cash"])
            if data.get("last_shown_price_cash") is not None
            else None
        ),
    )


class ConversationRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_phone(
        self, phone: str, *, instance_name: str
    ) -> asyncpg.Record | None:
        sql = f'''
            SELECT *
            FROM "{SCHEMA}"."Conversation"
            WHERE "phone" = $1 AND "instanceName" = $2
            LIMIT 1
        '''
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(sql, phone, instance_name)

    async def get_by_id(self, conversation_id: str) -> asyncpg.Record | None:
        sql = f'''SELECT * FROM "{SCHEMA}"."Conversation" WHERE "id" = $1'''
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(sql, conversation_id)

    async def upsert_conversation(
        self,
        *,
        phone: str,
        instance_name: str,
        language: str | None = None,
    ) -> asyncpg.Record:
        existing = await self.get_by_phone(phone, instance_name=instance_name)
        if existing:
            return existing
        cid = _new_id()
        now = _now()
        sql = f'''
            INSERT INTO "{SCHEMA}"."Conversation"
              ("id", "phone", "instanceName", "botStatus", "language",
               "activeLeadIds", "createdAt", "updatedAt")
            VALUES ($1, $2, $3, 'BOT_ACTIVE', $4, ARRAY[]::TEXT[], $5, $5)
            ON CONFLICT ("instanceName", "phone") DO UPDATE
              SET "updatedAt" = EXCLUDED."updatedAt"
            RETURNING *
        '''
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(sql, cid, phone, instance_name, language, now)

    async def save_canonical_state(
        self,
        conversation_id: str,
        state: ConversationCanonicalState,
    ) -> None:
        now = _now()
        sql = f'''
            UPDATE "{SCHEMA}"."Conversation"
            SET "canonicalStateJson" = $2::jsonb,
                "botStatus" = $3::"{SCHEMA}"."ConversationBotStatus",
                "language" = $4,
                "activeLeadIds" = $5,
                "handoffAt" = CASE
                    WHEN $3::text IN ('HANDOFF_SENT', 'HUMAN_ACTIVE')
                         AND "handoffAt" IS NULL THEN $6
                    ELSE "handoffAt"
                END,
                "updatedAt" = $6
            WHERE "id" = $1
        '''
        async with self._pool.acquire() as conn:
            await conn.execute(
                sql,
                conversation_id,
                canonical_state_to_json(state),
                state.lifecycle.status.value,
                state.language if state.language != "unknown" else None,
                state.active_lead_ids,
                now,
            )

    async def load_canonical_state(
        self, conversation_id: str
    ) -> ConversationCanonicalState | None:
        row = await self.get_by_id(conversation_id)
        if row is None:
            return None
        return canonical_state_from_json(
            row["canonicalStateJson"],
            thread_id=row["id"],
            phone=row["phone"],
            bot_status=row["botStatus"],
            active_lead_ids=list(row["activeLeadIds"] or []),
        )

    async def reset_conversation_memory(
        self,
        conversation_id: str,
        *,
        phone: str,
    ) -> ConversationCanonicalState:
        """Wipe conversational memory for a thread — fresh BOT_ACTIVE state.

        Clears canonical JSON, summary, handoff, and active lead links on the
        Conversation row. Does not delete historical Message/Lead rows (audit).
        """
        fresh = ConversationCanonicalState(
            thread_id=conversation_id,
            customer=CustomerState(phone=phone),
        )
        now = _now()
        sql = f'''
            UPDATE "{SCHEMA}"."Conversation"
            SET "canonicalStateJson" = $2::jsonb,
                "botStatus" = 'BOT_ACTIVE'::"{SCHEMA}"."ConversationBotStatus",
                "language" = NULL,
                "accumulatedSummary" = NULL,
                "activeLeadIds" = ARRAY[]::TEXT[],
                "handoffAt" = NULL,
                "updatedAt" = $3
            WHERE "id" = $1
        '''
        async with self._pool.acquire() as conn:
            await conn.execute(
                sql,
                conversation_id,
                canonical_state_to_json(fresh),
                now,
            )
        return fresh

    async def list_pending_messages(self, *, limit: int = 20) -> list[asyncpg.Record]:
        sql = f'''
            SELECT m.*, c."phone" AS "conversationPhone",
                   c."botStatus" AS "conversationBotStatus",
                   c."instanceName" AS "conversationInstance"
            FROM "{SCHEMA}"."Message" m
            JOIN "{SCHEMA}"."Conversation" c ON c."id" = m."conversationId"
            WHERE m."processingStatus" = 'PENDING'
              AND m."direction" = 'INBOUND'
              AND m."fromMe" = false
            ORDER BY m."createdAt" ASC
            LIMIT $1
        '''
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, limit)
            return list(rows)

    async def list_batch_work_seeds(self, *, limit: int = 20) -> list[asyncpg.Record]:
        """One seed row per conversation that needs a coalesce pass.

        Prefers ERROR batches awaiting retry (outbound not confirmed), then
        oldest PENDING. Does not load every PENDING of a conversation here —
        claim happens after quiet window with an explicit cutoff.
        """
        sql = f'''
            WITH ranked AS (
              SELECT m.*, c."phone" AS "conversationPhone",
                     c."botStatus" AS "conversationBotStatus",
                     c."instanceName" AS "conversationInstance",
                     ROW_NUMBER() OVER (
                       PARTITION BY m."conversationId"
                       ORDER BY
                         CASE
                           WHEN m."processingStatus" = 'ERROR'
                                AND COALESCE(
                                      m."turnFactsJson"->'_sdr_batch'->'result'->>'outbound_sent',
                                      'false'
                                    ) <> 'true'
                           THEN 0
                           WHEN m."processingStatus" = 'PENDING' THEN 1
                           ELSE 2
                         END,
                         m."createdAt" ASC,
                         m."id" ASC
                     ) AS rn
              FROM "{SCHEMA}"."Message" m
              JOIN "{SCHEMA}"."Conversation" c ON c."id" = m."conversationId"
              WHERE m."direction" = 'INBOUND'
                AND m."fromMe" = false
                AND (
                  m."processingStatus" = 'PENDING'
                  OR (
                    m."processingStatus" = 'ERROR'
                    AND m."turnFactsJson" ? '_sdr_batch'
                    AND COALESCE(
                          m."turnFactsJson"->'_sdr_batch'->'result'->>'outbound_sent',
                          'false'
                        ) <> 'true'
                  )
                )
            )
            SELECT * FROM ranked WHERE rn = 1
            ORDER BY "createdAt" ASC
            LIMIT $1
        '''
        async with self._pool.acquire() as conn:
            return list(await conn.fetch(sql, limit))

    async def list_pending_inbound_up_to(
        self,
        conversation_id: str,
        *,
        cutoff: datetime,
    ) -> list[asyncpg.Record]:
        """PENDING inbound for conversation with createdAt <= cutoff."""
        cutoff_naive = cutoff
        if cutoff.tzinfo is not None:
            cutoff_naive = cutoff.astimezone(timezone.utc).replace(tzinfo=None)
        sql = f'''
            SELECT *
            FROM "{SCHEMA}"."Message"
            WHERE "conversationId" = $1
              AND "processingStatus" = 'PENDING'
              AND "direction" = 'INBOUND'
              AND "fromMe" = false
              AND "createdAt" <= $2
            ORDER BY "createdAt" ASC, "id" ASC
        '''
        async with self._pool.acquire() as conn:
            return list(await conn.fetch(sql, conversation_id, cutoff_naive))

    async def get_messages_by_ids(self, message_ids: list[str]) -> list[asyncpg.Record]:
        if not message_ids:
            return []
        sql = f'''
            SELECT *
            FROM "{SCHEMA}"."Message"
            WHERE "id" = ANY($1::text[])
        '''
        async with self._pool.acquire() as conn:
            rows = list(await conn.fetch(sql, message_ids))
        # Preserve caller canonical order.
        by_id = {str(r["id"]): r for r in rows}
        return [by_id[mid] for mid in message_ids if mid in by_id]

    async def claim_inbound_batch(
        self,
        *,
        conversation_id: str,
        cutoff: datetime,
        batch_id: str,
        phone: str,
        instance_name: str,
    ) -> list[asyncpg.Record]:
        """Atomically claim PENDING rows with createdAt <= cutoff → PROCESSING.

        Returns claimed rows in canonical order. Empty if nothing to claim.
        """
        import json as _json

        cutoff_naive = cutoff
        if cutoff.tzinfo is not None:
            cutoff_naive = cutoff.astimezone(timezone.utc).replace(tzinfo=None)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                rows = list(
                    await conn.fetch(
                        f'''
                        SELECT *
                        FROM "{SCHEMA}"."Message"
                        WHERE "conversationId" = $1
                          AND "processingStatus" = 'PENDING'
                          AND "direction" = 'INBOUND'
                          AND "fromMe" = false
                          AND "createdAt" <= $2
                        ORDER BY "createdAt" ASC, "id" ASC
                        FOR UPDATE SKIP LOCKED
                        ''',
                        conversation_id,
                        cutoff_naive,
                    )
                )
                if not rows:
                    return []
                message_ids = [str(r["id"]) for r in rows]
                anchor = message_ids[0]
                batch = InboundBatch(
                    batch_id=batch_id,
                    conversation_id=conversation_id,
                    phone=phone,
                    instance_name=instance_name,
                    anchor_message_id=anchor,
                    cutoff=cutoff_naive,
                    message_ids=message_ids,
                    segments=[],
                    status=BatchStatus.PROCESSING,
                )
                for order, row in enumerate(rows):
                    payload = {BATCH_JSON_KEY: batch.member_payload(str(row["id"]), order=order)}
                    merged = _json.dumps(
                        merge_turn_facts(row["turnFactsJson"], payload),
                        ensure_ascii=False,
                    )
                    await conn.execute(
                        f'''
                        UPDATE "{SCHEMA}"."Message"
                        SET "processingStatus" = 'PROCESSING',
                            "turnFactsJson" = $2::jsonb
                        WHERE "id" = $1
                          AND "processingStatus" = 'PENDING'
                        ''',
                        str(row["id"]),
                        merged,
                    )
                claimed = list(
                    await conn.fetch(
                        f'''
                        SELECT * FROM "{SCHEMA}"."Message"
                        WHERE "id" = ANY($1::text[])
                        ORDER BY "createdAt" ASC, "id" ASC
                        ''',
                        message_ids,
                    )
                )
                return claimed

    async def reclaim_error_batch(
        self,
        *,
        message_ids: list[str],
        batch_meta: dict,
    ) -> list[asyncpg.Record]:
        """Re-claim the exact ERROR batch membership for retry (same IDs)."""
        import json as _json

        if not message_ids:
            return []
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                rows = list(
                    await conn.fetch(
                        f'''
                        SELECT * FROM "{SCHEMA}"."Message"
                        WHERE "id" = ANY($1::text[])
                        ORDER BY "createdAt" ASC, "id" ASC
                        FOR UPDATE
                        ''',
                        message_ids,
                    )
                )
                result = (batch_meta.get("result") or {}) if isinstance(batch_meta, dict) else {}
                if result.get("outbound_sent") is True:
                    return rows
                for order, row in enumerate(rows):
                    meta = dict(batch_meta)
                    meta["order"] = order
                    meta["status"] = "PROCESSING"
                    merged = _json.dumps(
                        merge_turn_facts(row["turnFactsJson"], {BATCH_JSON_KEY: meta}),
                        ensure_ascii=False,
                    )
                    await conn.execute(
                        f'''
                        UPDATE "{SCHEMA}"."Message"
                        SET "processingStatus" = 'PROCESSING',
                            "turnFactsJson" = $2::jsonb
                        WHERE "id" = $1
                        ''',
                        str(row["id"]),
                        merged,
                    )
                return list(
                    await conn.fetch(
                        f'''
                        SELECT * FROM "{SCHEMA}"."Message"
                        WHERE "id" = ANY($1::text[])
                        ORDER BY "createdAt" ASC, "id" ASC
                        ''',
                        message_ids,
                    )
                )

    async def finalize_batch_messages(
        self,
        message_ids: list[str],
        *,
        status: str,
        batch_patch: dict,
    ) -> None:
        """Set status + merge ``_sdr_batch`` on every member (preserves ``_sdr_media``)."""
        import json as _json

        if not message_ids:
            return
        now = _now()
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                rows = await conn.fetch(
                    f'''SELECT "id", "turnFactsJson" FROM "{SCHEMA}"."Message"
                        WHERE "id" = ANY($1::text[])''',
                    message_ids,
                )
                for row in rows:
                    merged = _json.dumps(
                        merge_turn_facts(
                            row["turnFactsJson"], {BATCH_JSON_KEY: batch_patch}
                        ),
                        ensure_ascii=False,
                    )
                    await conn.execute(
                        f'''
                        UPDATE "{SCHEMA}"."Message"
                        SET "processingStatus" = $2,
                            "processedAt" = $3,
                            "turnFactsJson" = $4::jsonb
                        WHERE "id" = $1
                        ''',
                        str(row["id"]),
                        status,
                        now,
                        merged,
                    )

    async def mark_message_processed(
        self,
        message_id: str,
        *,
        status: str = "DONE",
        turn_facts_json: str | None = None,
    ) -> None:
        now = _now()
        if turn_facts_json is None:
            sql = f'''
                UPDATE "{SCHEMA}"."Message"
                SET "processingStatus" = $2,
                    "processedAt" = $3
                WHERE "id" = $1
            '''
            async with self._pool.acquire() as conn:
                await conn.execute(sql, message_id, status, now)
            return

        # Merge into existing JSON so _sdr_media / _sdr_batch survive.
        from sdr.domain.inbound_batch import merge_turn_facts
        import json as _json

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f'''SELECT "turnFactsJson" FROM "{SCHEMA}"."Message" WHERE "id" = $1''',
                message_id,
            )
            existing = row["turnFactsJson"] if row else None
            try:
                patch = _json.loads(turn_facts_json)
            except Exception:
                patch = {"_raw": turn_facts_json}
            if not isinstance(patch, dict):
                patch = {"value": patch}
            merged = _json.dumps(merge_turn_facts(existing, patch), ensure_ascii=False)
            await conn.execute(
                f'''
                UPDATE "{SCHEMA}"."Message"
                SET "processingStatus" = $2,
                    "processedAt" = $3,
                    "turnFactsJson" = $4::jsonb
                WHERE "id" = $1
                ''',
                message_id,
                status,
                now,
                merged,
            )

    async def mark_message_skipped(self, message_id: str, *, reason: str) -> None:
        await self.mark_message_processed(
            message_id,
            status=f"SKIPPED:{reason}"[:64],
        )

    async def save_transcription(self, message_id: str, transcription: str) -> None:
        """Persist Whisper transcription result on the Message row."""
        sql = f'''
            UPDATE "{SCHEMA}"."Message"
            SET "transcription" = $2
            WHERE "id" = $1
        '''
        async with self._pool.acquire() as conn:
            await conn.execute(sql, message_id, transcription)

    async def list_recent_turns(
        self,
        conversation_id: str,
        *,
        limit: int = 5,
        exclude_message_ids: list[str] | None = None,
    ) -> list[dict[str, str]]:
        """Return the last ``limit`` messages as [{role, text}] for LLM context.

        Only messages with non-empty text are included. Outbound bot messages
        are labeled "julia"; inbound customer messages are labeled "customer".
        Order: oldest first (chronological), so the LLM sees the natural flow.

        ``exclude_message_ids``: Prisma Message ids (cuid / text) of the current
        inbound batch. These rows are excluded so the current turn's messages
        are not duplicated in the history that the Understanding LLM receives
        alongside the live inbound. Cast as text[] — Message.id is not uuid.
        """
        if exclude_message_ids:
            sql = f'''
                SELECT "direction", "fromMe", "isBotSent", "text"
                FROM "{SCHEMA}"."Message"
                WHERE "conversationId" = $1
                  AND "text" IS NOT NULL
                  AND "text" <> ''
                  AND "id" != ALL($3::text[])
                ORDER BY "createdAt" DESC, "id" DESC
                LIMIT $2
            '''
            async with self._pool.acquire() as conn:
                rows = list(await conn.fetch(sql, conversation_id, limit, exclude_message_ids))
        else:
            sql = f'''
                SELECT "direction", "fromMe", "isBotSent", "text"
                FROM "{SCHEMA}"."Message"
                WHERE "conversationId" = $1
                  AND "text" IS NOT NULL
                  AND "text" <> ''
                ORDER BY "createdAt" DESC, "id" DESC
                LIMIT $2
            '''
            async with self._pool.acquire() as conn:
                rows = list(await conn.fetch(sql, conversation_id, limit))

        turns: list[dict[str, str]] = []
        for row in reversed(rows):
            text = str(row["text"] or "").strip()
            if not text:
                continue
            direction = str(row["direction"] or "")
            is_bot = bool(row["isBotSent"] or False)
            from_me = bool(row["fromMe"] or False)
            if direction == "OUTBOUND" and (is_bot or from_me):
                role = "julia"
            else:
                role = "customer"
            turns.append({"role": role, "text": text})
        return turns

    async def insert_bot_outbound(
        self,
        *,
        conversation_id: str,
        instance_name: str,
        text: str,
        provider_message_id: str | None = None,
        content_type: str = "TEXT",
    ) -> str:
        """Persist bot outbound before/after Evolution send for fromMe dedupe."""
        import uuid

        now = _now()
        msg_id = str(uuid.uuid4())
        provider_id = provider_message_id or f"bot-{msg_id}"
        ctype = (content_type or "TEXT").upper()
        if ctype not in {"TEXT", "IMAGE", "AUDIO", "DOCUMENT", "VIDEO", "STICKER"}:
            ctype = "TEXT"
        sql = f'''
            INSERT INTO "{SCHEMA}"."Message"
              ("id", "conversationId", "providerMessageId", "instanceName",
               "direction", "contentType", "text", "fromMe", "isHumanSent",
               "isBotSent", "processingStatus", "createdAt", "processedAt")
            VALUES (
              $1, $2, $3, $4,
              'OUTBOUND'::"{SCHEMA}"."MessageDirection",
              $7::"{SCHEMA}"."MessageContentType",
              $5, true, false, true, 'DONE', $6, $6
            )
            ON CONFLICT ("instanceName", "providerMessageId") DO NOTHING
            RETURNING "id"
        '''
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                sql, msg_id, conversation_id, provider_id, instance_name, text, now, ctype
            )
            return str(row["id"]) if row else msg_id
