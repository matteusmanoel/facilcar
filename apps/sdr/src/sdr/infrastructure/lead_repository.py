"""Lead + FinancingRequest / SellRequest persistence (asyncpg)."""

from __future__ import annotations

import json
import logging
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
from sdr.domain.vendor_summary import build_vendor_summary, is_placeholder_display_name

SCHEMA = "facilcar"
logger = logging.getLogger(__name__)

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
    """Seller-facing brief persisted on Lead.juliaSummary."""
    return build_vendor_summary(state)


class LeadRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_by_id(self, lead_id: str) -> asyncpg.Record | None:
        sql = f'''SELECT * FROM "{SCHEMA}"."Lead" WHERE "id" = $1'''
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(sql, lead_id)

    async def list_linked_vehicle_titles(self, lead_ids: list[str]) -> list[str]:
        """Titles already linked in CRM (interest table + primary vehicleId)."""
        if not lead_ids:
            return []
        sql = f'''
            SELECT title FROM (
              SELECT i."isPrimary" AS is_primary, i."createdAt" AS created_at, v."title" AS title
              FROM "{SCHEMA}"."LeadVehicleInterest" i
              JOIN "{SCHEMA}"."Vehicle" v ON v."id" = i."vehicleId"
              WHERE i."leadId" = ANY($1::text[])
              UNION ALL
              SELECT true AS is_primary, l."createdAt" AS created_at, v."title" AS title
              FROM "{SCHEMA}"."Lead" l
              JOIN "{SCHEMA}"."Vehicle" v ON v."id" = l."vehicleId"
              WHERE l."id" = ANY($1::text[])
                AND l."vehicleId" IS NOT NULL
                AND NOT EXISTS (
                  SELECT 1 FROM "{SCHEMA}"."LeadVehicleInterest" i2
                  WHERE i2."leadId" = l."id" AND i2."vehicleId" = l."vehicleId"
                )
            ) linked
            ORDER BY is_primary DESC, created_at ASC
        '''
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, lead_ids)
        except asyncpg.UndefinedTableError:
            logger.warning("LeadVehicleInterest not migrated yet; skipping linked titles")
            return []
        titles: list[str] = []
        seen: set[str] = set()
        for row in rows:
            title = str(row["title"] or "").strip()
            if title and title not in seen:
                seen.add(title)
                titles.append(title)
        return titles

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
            await self._sync_shown_vehicles(conn, lead_id, list(state.last_shown_vehicle_ids))
            if not is_placeholder_display_name(name):
                await self._sync_lead_name(conn, lead_id, name.strip())
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
            await self._sync_shown_vehicles(conn, lead_id, list(state.last_shown_vehicle_ids))
            if not is_placeholder_display_name(state.customer.name):
                await self._sync_lead_name(conn, lead_id, state.customer.name.strip())
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

    async def sync_names_for_customer(self, customer_id: str, name: str) -> None:
        """Upgrade CRM display names when a real name replaces a placeholder."""
        cleaned = (name or "").strip()
        if is_placeholder_display_name(cleaned):
            return
        now = _now()
        sql = f'''
            UPDATE "{SCHEMA}"."Lead"
            SET "name" = $2, "updatedAt" = $3
            WHERE "customerId" = $1
              AND "deletedAt" IS NULL
        '''
        async with self._pool.acquire() as conn:
            await conn.execute(sql, customer_id, cleaned, now)

    async def _sync_lead_name(
        self,
        conn: asyncpg.Connection,
        lead_id: str,
        name: str,
    ) -> None:
        cleaned = (name or "").strip()
        if is_placeholder_display_name(cleaned):
            return
        await conn.execute(
            f'''
            UPDATE "{SCHEMA}"."Lead"
            SET "name" = $2, "updatedAt" = $3
            WHERE "id" = $1 AND "deletedAt" IS NULL
            ''',
            lead_id,
            cleaned,
            _now(),
        )

    async def _sync_shown_vehicles(
        self,
        conn: asyncpg.Connection,
        lead_id: str,
        vehicle_ids: list[str],
    ) -> None:
        """Persist published vehicles Júlia actually presented — never string-guess."""
        ids = [str(v).strip() for v in vehicle_ids if str(v).strip()]
        if not ids:
            return
        try:
            published = await conn.fetch(
                f'''
                SELECT "id" FROM "{SCHEMA}"."Vehicle"
                WHERE "id" = ANY($1::text[])
                  AND "status" = 'PUBLISHED'::"{SCHEMA}"."VehicleStatus"
                ''',
                ids,
            )
        except asyncpg.UndefinedTableError:
            logger.warning("Vehicle table unavailable; skipping CRM vehicle sync")
            return
        published_set = {str(row["id"]) for row in published}
        ordered = [vid for vid in ids if vid in published_set]
        if not ordered:
            return
        primary = ordered[0]
        await conn.execute(
            f'''
            UPDATE "{SCHEMA}"."Lead"
            SET "vehicleId" = $2, "updatedAt" = $3
            WHERE "id" = $1
            ''',
            lead_id,
            primary,
            _now(),
        )
        try:
            await conn.execute(
                f'''
                UPDATE "{SCHEMA}"."LeadVehicleInterest"
                SET "isPrimary" = false
                WHERE "leadId" = $1
                ''',
                lead_id,
            )
            for index, vid in enumerate(ordered):
                await conn.execute(
                    f'''
                    INSERT INTO "{SCHEMA}"."LeadVehicleInterest"
                      ("id", "leadId", "vehicleId", "isPrimary", "createdAt")
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT ("leadId", "vehicleId") DO UPDATE
                      SET "isPrimary" = EXCLUDED."isPrimary"
                    ''',
                    _new_id(),
                    lead_id,
                    vid,
                    index == 0,
                    _now(),
                )
        except asyncpg.UndefinedTableError:
            logger.warning("LeadVehicleInterest not migrated yet; primary vehicleId still set")

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
