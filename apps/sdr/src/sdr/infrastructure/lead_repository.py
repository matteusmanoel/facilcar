"""Lead + FinancingRequest / SellRequest persistence (asyncpg)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from sdr.domain.phone import normalize_phone
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    LeadTemperature,
)

SCHEMA = "facilcar"

INTENT_TO_LEAD_TYPE: dict[BusinessIntent, str] = {
    BusinessIntent.PURCHASE: "VEHICLE_INTEREST",
    BusinessIntent.PURCHASE_FINANCING: "FINANCING",
    BusinessIntent.TRADE: "TRADE_IN",
    BusinessIntent.SALE: "SELL_VEHICLE",
    BusinessIntent.CONSIGNMENT: "CONSIGNMENT",
    BusinessIntent.REFINANCING: "REFINANCING",
}


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def build_julia_summary(state: ConversationCanonicalState) -> str:
    parts = [
        f"Intent: {state.intent.value}",
        f"Business: {state.business.type.value}",
        f"Actionability: {state.business.actionability.value}",
    ]
    if state.lifecycle.handoff_reason:
        parts.append(f"Handoff: {state.lifecycle.handoff_reason}")
    if state.facts:
        compact = {k: v for k, v in state.facts.items() if v is not None}
        parts.append(f"Facts: {json.dumps(compact, ensure_ascii=False)}")
    return " | ".join(parts)


class LeadRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_by_id(self, lead_id: str) -> asyncpg.Record | None:
        sql = f'''SELECT * FROM "{SCHEMA}"."Lead" WHERE "id" = $1'''
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(sql, lead_id)

    async def create_from_state(
        self,
        state: ConversationCanonicalState,
        *,
        customer_id: str | None,
        conversation_id: str,
        name: str,
    ) -> asyncpg.Record | None:
        """Create Lead only for commercial intent (not greeting/smalltalk)."""
        if state.intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK):
            return None

        lead_type = INTENT_TO_LEAD_TYPE.get(state.intent, "CONTACT")
        phone = normalize_phone(state.customer.phone)
        now = _now()
        lead_id = _new_id()
        temperature = (
            state.temperature.value
            if state.temperature
            else LeadTemperature.WARM.value
        )
        summary = build_julia_summary(state)

        sql = f'''
            INSERT INTO "{SCHEMA}"."Lead"
              ("id", "type", "status", "source", "channel", "name", "phone",
               "whatsapp", "customerId", "conversationId", "juliaSummary",
               "temperature", "message", "metadataJson", "createdAt", "updatedAt")
            VALUES (
              $1,
              $2::"{SCHEMA}"."LeadType",
              'NEW'::"{SCHEMA}"."LeadStatus",
              'WHATSAPP'::"{SCHEMA}"."LeadSource",
              'WHATSAPP'::"{SCHEMA}"."LeadChannel",
              $3, $4, $4, $5, $6, $7,
              $8::"{SCHEMA}"."LeadTemperature",
              $9, $10::jsonb, $11, $11
            )
            RETURNING *
        '''
        meta = {"intent": state.intent.value, "facts": state.facts}
        async with self._pool.acquire() as conn:
            lead = await conn.fetchrow(
                sql,
                lead_id,
                lead_type,
                name,
                phone,
                customer_id,
                conversation_id,
                summary,
                temperature,
                summary,
                json.dumps(meta, ensure_ascii=False),
                now,
            )
            await self._upsert_side_tables(conn, lead_id, state)
            return lead

    async def mark_qualified_for_handoff(
        self,
        lead_id: str,
        state: ConversationCanonicalState,
    ) -> asyncpg.Record | None:
        """Handoff: status QUALIFIED, juliaSummary set, assignedToUserId = null."""
        now = _now()
        summary = build_julia_summary(state)
        temperature = (
            state.temperature.value
            if state.temperature
            else LeadTemperature.WARM.value
        )
        sql = f'''
            UPDATE "{SCHEMA}"."Lead"
            SET "status" = 'QUALIFIED'::"{SCHEMA}"."LeadStatus",
                "juliaSummary" = $2,
                "temperature" = $3::"{SCHEMA}"."LeadTemperature",
                "assignedToUserId" = NULL,
                "updatedAt" = $4
            WHERE "id" = $1
            RETURNING *
        '''
        async with self._pool.acquire() as conn:
            lead = await conn.fetchrow(sql, lead_id, summary, temperature, now)
            await self._upsert_side_tables(conn, lead_id, state)
            if lead is not None:
                await conn.execute(
                    f'''
                    INSERT INTO "{SCHEMA}"."SdrNotification"
                      ("id", "leadId", "type", "createdAt")
                    VALUES ($1, $2, 'NEW_QUALIFIED'::"{SCHEMA}"."SdrNotificationType", $3)
                    ''',
                    _new_id(),
                    lead_id,
                    now,
                )
            return lead

    async def _upsert_side_tables(
        self,
        conn: asyncpg.Connection,
        lead_id: str,
        state: ConversationCanonicalState,
    ) -> None:
        facts = state.facts
        if state.intent in (
            BusinessIntent.PURCHASE_FINANCING,
            BusinessIntent.REFINANCING,
        ):
            await self._upsert_financing(conn, lead_id, facts)
        if state.intent in (
            BusinessIntent.SALE,
            BusinessIntent.CONSIGNMENT,
            BusinessIntent.TRADE,
        ):
            await self._upsert_sell(conn, lead_id, facts)

    async def _upsert_financing(
        self,
        conn: asyncpg.Connection,
        lead_id: str,
        facts: dict[str, Any],
    ) -> None:
        existing = await conn.fetchrow(
            f'''SELECT "id" FROM "{SCHEMA}"."FinancingRequest" WHERE "leadId" = $1''',
            lead_id,
        )
        cpf = facts.get("cpf")
        vehicle_model = (
            facts.get("desired_model")
            or facts.get("vehicle_model")
            or facts.get("model")
        )
        vehicle_year = facts.get("vehicle_year") or facts.get("year")
        notes = facts.get("notes")
        if existing:
            await conn.execute(
                f'''
                UPDATE "{SCHEMA}"."FinancingRequest"
                SET "cpf" = COALESCE($2, "cpf"),
                    "vehicleModel" = COALESCE($3, "vehicleModel"),
                    "vehicleYear" = COALESCE($4, "vehicleYear"),
                    "notes" = COALESCE($5, "notes")
                WHERE "leadId" = $1
                ''',
                lead_id,
                cpf,
                vehicle_model,
                int(vehicle_year) if vehicle_year is not None else None,
                notes,
            )
            return
        await conn.execute(
            f'''
            INSERT INTO "{SCHEMA}"."FinancingRequest"
              ("id", "leadId", "cpf", "vehicleModel", "vehicleYear", "notes")
            VALUES ($1, $2, $3, $4, $5, $6)
            ''',
            _new_id(),
            lead_id,
            cpf,
            vehicle_model,
            int(vehicle_year) if vehicle_year is not None else None,
            notes,
        )

    async def _upsert_sell(
        self,
        conn: asyncpg.Connection,
        lead_id: str,
        facts: dict[str, Any],
    ) -> None:
        existing = await conn.fetchrow(
            f'''SELECT "id" FROM "{SCHEMA}"."SellRequest" WHERE "leadId" = $1''',
            lead_id,
        )
        brand = facts.get("brand")
        model = (
            facts.get("sell_model")
            or facts.get("trade_model")
            or facts.get("vehicle_model")
            or facts.get("model")
        )
        year = facts.get("sell_year") or facts.get("trade_year") or facts.get("year")
        mileage = facts.get("mileage") or facts.get("km")
        observations = facts.get("observations") or facts.get("notes")
        if existing:
            await conn.execute(
                f'''
                UPDATE "{SCHEMA}"."SellRequest"
                SET "brand" = COALESCE($2, "brand"),
                    "model" = COALESCE($3, "model"),
                    "yearModel" = COALESCE($4, "yearModel"),
                    "mileage" = COALESCE($5, "mileage"),
                    "observations" = COALESCE($6, "observations")
                WHERE "leadId" = $1
                ''',
                lead_id,
                brand,
                model,
                int(year) if year is not None else None,
                int(mileage) if mileage is not None else None,
                observations,
            )
            return
        await conn.execute(
            f'''
            INSERT INTO "{SCHEMA}"."SellRequest"
              ("id", "leadId", "brand", "model", "yearModel", "mileage", "observations")
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ''',
            _new_id(),
            lead_id,
            brand,
            model,
            int(year) if year is not None else None,
            int(mileage) if mileage is not None else None,
            observations,
        )
