"""Lead + FinancingRequest / SellRequest persistence (asyncpg)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg

from sdr.domain.commercial_snapshot import (
    build_commercial_snapshot,
)
from sdr.domain.phone import normalize_phone
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    LeadTemperature,
)
from sdr.domain.vendor_summary import build_vendor_summary, is_placeholder_display_name

SCHEMA = "facilcar"
logger = logging.getLogger(__name__)


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_birth_date_for_db(value: Any) -> datetime | None:
    """Parse DD/MM/AAAA or AAAA-MM-DD into a naive datetime for FinancingRequest.birthDate."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    import re

    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(year, month, day)
        except ValueError:
            return None
    m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if m2:
        year, month, day = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        try:
            return datetime(year, month, day)
        except ValueError:
            return None
    return None


def _parse_visit_date(value: Any) -> datetime | None:
    return _parse_birth_date_for_db(value)


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
        first_inbound: str | None = None,
    ) -> asyncpg.Record | None:
        """Create Lead only for commercial intent (not greeting/smalltalk)."""
        if state.intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK):
            return None

        snapshot = build_commercial_snapshot(state, first_inbound=first_inbound, qualify=False)
        lead_type = snapshot.lead_type
        phone = normalize_phone(state.customer.phone)
        now = _now()
        lead_id = _new_id()
        temperature = snapshot.temperature or LeadTemperature.WARM.value
        display_name = name if not is_placeholder_display_name(name) else (snapshot.name or name)

        sql = f'''
            INSERT INTO "{SCHEMA}"."Lead"
              ("id", "type", "status", "source", "channel", "name", "phone",
               "whatsapp", "customerId", "conversationId", "juliaSummary",
               "temperature", "message", "city", "state", "metadataJson",
               "commercialRevision", "createdAt", "updatedAt")
            VALUES (
              $1,
              $2::"{SCHEMA}"."LeadType",
              'NEW'::"{SCHEMA}"."LeadStatus",
              'WHATSAPP'::"{SCHEMA}"."LeadSource",
              'WHATSAPP'::"{SCHEMA}"."LeadChannel",
              $3, $4, $4, $5, $6, $7,
              $8::"{SCHEMA}"."LeadTemperature",
              $9, $10, $11, $12::jsonb, $13, $14, $14
            )
            RETURNING *
        '''
        async with self._pool.acquire() as conn:
            lead = await conn.fetchrow(
                sql,
                lead_id,
                lead_type,
                display_name,
                phone,
                customer_id,
                conversation_id,
                snapshot.julia_summary,
                temperature,
                snapshot.original_message,
                snapshot.city,
                snapshot.state,
                json.dumps(snapshot.metadata, ensure_ascii=False),
                snapshot.revision,
                now,
            )
            await self._apply_snapshot_side_effects(conn, lead_id, state, snapshot, conversation_id)
            if not is_placeholder_display_name(display_name):
                await self._sync_lead_name(conn, lead_id, display_name.strip())
            return lead

    async def sync_from_state(
        self,
        lead_id: str,
        state: ConversationCanonicalState,
        *,
        qualify: bool = False,
        first_inbound: str | None = None,
        conversation_id: str | None = None,
    ) -> asyncpg.Record | None:
        """Idempotent CRM flush from consolidated canonical state.

        Stale revisions (commercialRevision < stored) are ignored. Handoff
        qualifies once; later commercial updates refresh facts without a
        second NEW_QUALIFIED notification.
        """
        now = _now()
        async with self._pool.acquire() as conn:
            current = await conn.fetchrow(
                f'''
                SELECT "id", "status", "commercialRevision", "message", "conversationId"
                FROM "{SCHEMA}"."Lead"
                WHERE "id" = $1 AND "deletedAt" IS NULL
                ''',
                lead_id,
            )
            if current is None:
                return None
            already = str(current["status"]) == "QUALIFIED"
            snapshot = build_commercial_snapshot(
                state,
                first_inbound=first_inbound,
                qualify=qualify,
                already_qualified=already,
            )
            stored_rev = int(current["commercialRevision"] or 0)
            if snapshot.revision < stored_rev:
                return current
            temperature = snapshot.temperature or LeadTemperature.WARM.value
            status_sql = (
                f'''"status" = 'QUALIFIED'::"{SCHEMA}"."LeadStatus",'''
                if qualify or already
                else ""
            )
            sql = f'''
                UPDATE "{SCHEMA}"."Lead"
                SET {status_sql}
                    "juliaSummary" = $2,
                    "temperature" = $3::"{SCHEMA}"."LeadTemperature",
                    "assignedToUserId" = CASE WHEN $8 THEN NULL ELSE "assignedToUserId" END,
                    "city" = COALESCE($5, "city"),
                    "state" = COALESCE($6, "state"),
                    "metadataJson" = $7::jsonb,
                    "commercialRevision" = $9,
                    "updatedAt" = $4
                WHERE "id" = $1
                  AND "commercialRevision" <= $9
                RETURNING *
            '''
            lead = await conn.fetchrow(
                sql,
                lead_id,
                snapshot.julia_summary,
                temperature,
                now,
                snapshot.city,
                snapshot.state,
                json.dumps(snapshot.metadata, ensure_ascii=False),
                bool(qualify),
                snapshot.revision,
            )
            if lead is None:
                return current
            conv_id = conversation_id or current["conversationId"]
            await self._apply_snapshot_side_effects(conn, lead_id, state, snapshot, conv_id)
            if not is_placeholder_display_name(state.customer.name):
                await self._sync_lead_name(conn, lead_id, state.customer.name.strip())
            if qualify and not already:
                exists = await conn.fetchrow(
                    f'''
                    SELECT 1 FROM "{SCHEMA}"."SdrNotification"
                    WHERE "leadId" = $1
                      AND "type" = 'NEW_QUALIFIED'::"{SCHEMA}"."SdrNotificationType"
                    LIMIT 1
                    ''',
                    lead_id,
                )
                if exists is None:
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
                try:
                    await self._notify_failed_document_uploads(conn, lead_id, now)
                except Exception:
                    logger.exception(
                        "document-upload-failed notification skipped lead=%s",
                        lead_id,
                    )
            return lead

    async def mark_qualified_for_handoff(
        self,
        lead_id: str,
        state: ConversationCanonicalState,
        *,
        first_inbound: str | None = None,
        conversation_id: str | None = None,
    ) -> asyncpg.Record | None:
        """Handoff: status QUALIFIED, juliaSummary set, assignedToUserId = null."""
        return await self.sync_from_state(
            lead_id,
            state,
            qualify=True,
            first_inbound=first_inbound,
            conversation_id=conversation_id,
        )

    async def _apply_snapshot_side_effects(
        self,
        conn: asyncpg.Connection,
        lead_id: str,
        state: ConversationCanonicalState,
        snapshot: Any,
        conversation_id: str | None,
    ) -> None:
        await self._upsert_side_tables(conn, lead_id, state)
        await self._sync_shown_vehicles(
            conn,
            lead_id,
            list(snapshot.interest_ids or state.last_shown_vehicle_ids),
            primary_vehicle_id=snapshot.primary_vehicle_id,
        )
        await self._upsert_visit(conn, lead_id, snapshot, conversation_id)

    async def notify_document_upload_failed(self, lead_id: str) -> None:
        try:
            async with self._pool.acquire() as conn:
                await self._notify_failed_document_uploads(conn, lead_id, _now())
        except Exception:
            logger.exception(
                "document-upload-failed notification skipped lead=%s",
                lead_id,
            )

    async def _notify_failed_document_uploads(
        self,
        conn: asyncpg.Connection,
        lead_id: str,
        now: datetime | None = None,
    ) -> None:
        """Bell for docs that extracted but were not stored — admin must attach manually."""
        created = now or _now()
        failed = await conn.fetch(
            f'''
            SELECT 1 FROM "{SCHEMA}"."SdrDocument"
            WHERE "leadId" = $1
              AND (
                "storageKey" = ''
                OR "storageKey" LIKE 'stub/%'
                OR "extractionStatus" = 'FAILED'::"{SCHEMA}"."SdrDocumentExtractionStatus"
              )
            LIMIT 1
            ''',
            lead_id,
        )
        if not failed:
            return
        await conn.execute(
            f'''
            INSERT INTO "{SCHEMA}"."SdrNotification"
              ("id", "leadId", "type", "createdAt")
            VALUES ($1, $2, 'DOCUMENT_UPLOAD_FAILED'::"{SCHEMA}"."SdrNotificationType", $3)
            ''',
            _new_id(),
            lead_id,
            created,
        )

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
        *,
        primary_vehicle_id: str | None = None,
    ) -> None:
        """Persist presented vehicles. Primary is explicit — never list position."""
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
        explicit = (primary_vehicle_id or "").strip() or None
        primary = explicit if explicit in published_set and explicit in ordered else None
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
            for vid in ordered:
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
                    vid == primary,
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
        payment = str(facts.get("payment_method") or "").strip().lower()
        if state.intent in (
            BusinessIntent.PURCHASE_FINANCING,
            BusinessIntent.REFINANCING,
        ) or payment == "financing":
            await self._upsert_financing(conn, lead_id, state)
        if state.intent in (
            BusinessIntent.SALE,
            BusinessIntent.CONSIGNMENT,
            BusinessIntent.TRADE,
        ):
            await self._upsert_sell(conn, lead_id, facts)

    async def _upsert_visit(
        self,
        conn: asyncpg.Connection,
        lead_id: str,
        snapshot: Any,
        conversation_id: str | None,
    ) -> None:
        visit = snapshot.visit
        if visit is None:
            return
        if not (
            visit.interest
            or visit.declined
            or visit.date
            or visit.time
            or visit.display
            or visit.raw
            or visit.location_sent
        ):
            return
        preferred = _parse_visit_date(visit.date)
        existing = await conn.fetchrow(
            f'''
            SELECT "id" FROM "{SCHEMA}"."VisitInterest"
            WHERE "leadId" = $1
            ORDER BY "createdAt" DESC
            LIMIT 1
            ''',
            lead_id,
        )
        if existing:
            await conn.execute(
                f'''
                UPDATE "{SCHEMA}"."VisitInterest"
                SET "conversationId" = COALESCE($1, "conversationId"),
                    "dateHint" = COALESCE($2, "dateHint"),
                    "period" = COALESCE($3, "period"),
                    "notes" = COALESCE($4, "notes"),
                    "preferredDate" = COALESCE($5, "preferredDate"),
                    "preferredTime" = COALESCE($6, "preferredTime"),
                    "originalText" = COALESCE($7, "originalText"),
                    "accepted" = COALESCE($8, "accepted"),
                    "declined" = COALESCE($9, "declined"),
                    "locationSent" = $10,
                    "interest" = $11
                WHERE "id" = $12
                ''',
                conversation_id,
                visit.display or visit.date,
                visit.period,
                visit.display,
                preferred,
                visit.time,
                visit.raw,
                visit.accepted if visit.accepted else None,
                visit.declined if visit.declined else None,
                bool(visit.location_sent),
                bool(visit.interest),
                existing["id"],
            )
            return
        await conn.execute(
            f'''
            INSERT INTO "{SCHEMA}"."VisitInterest"
              ("id", "leadId", "conversationId", "dateHint", "period", "notes",
               "preferredDate", "preferredTime", "originalText", "accepted",
               "declined", "locationSent", "interest", "createdAt")
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ''',
            _new_id(),
            lead_id,
            conversation_id,
            visit.display or visit.date,
            visit.period,
            visit.display,
            preferred,
            visit.time,
            visit.raw,
            visit.accepted if visit.accepted else None,
            visit.declined if visit.declined else None,
            bool(visit.location_sent),
            bool(visit.interest),
            _now(),
        )

    async def _upsert_financing(
        self,
        conn: asyncpg.Connection,
        lead_id: str,
        state: ConversationCanonicalState,
    ) -> None:
        from sdr.domain.commercial_snapshot import financing_snapshot

        fin = financing_snapshot(state)
        if fin is None:
            return
        existing = await conn.fetchrow(
            f'''SELECT "id" FROM "{SCHEMA}"."FinancingRequest" WHERE "leadId" = $1''',
            lead_id,
        )
        birth_dt = _parse_birth_date_for_db(fin.birth_date)
        # desiredInstallments is prazo (month count). Never write R$/mês there.
        installment_count = fin.desired_installments_count
        if existing:
            await conn.execute(
                f'''
                UPDATE "{SCHEMA}"."FinancingRequest"
                SET "cpf" = COALESCE($2, "cpf"),
                    "birthDate" = COALESCE($3, "birthDate"),
                    "downPayment" = COALESCE($4, "downPayment"),
                    "vehicleModel" = COALESCE($5, "vehicleModel"),
                    "vehicleYear" = COALESCE($6, "vehicleYear"),
                    "notes" = COALESCE($7, "notes"),
                    "hasDriverLicense" = COALESCE($8, "hasDriverLicense"),
                    "desiredMonthlyPayment" = COALESCE($9, "desiredMonthlyPayment"),
                    "desiredInstallments" = COALESCE($10, "desiredInstallments"),
                    "vehicleId" = COALESCE($11, "vehicleId")
                WHERE "leadId" = $1
                ''',
                lead_id,
                fin.cpf,
                birth_dt,
                fin.down_payment,
                fin.vehicle_model,
                fin.vehicle_year,
                fin.notes,
                fin.has_driver_license,
                fin.desired_monthly_payment,
                installment_count,
                fin.vehicle_id,
            )
            return
        await conn.execute(
            f'''
            INSERT INTO "{SCHEMA}"."FinancingRequest"
              ("id", "leadId", "cpf", "birthDate", "downPayment",
               "vehicleModel", "vehicleYear", "notes", "hasDriverLicense",
               "desiredMonthlyPayment", "desiredInstallments", "vehicleId")
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ''',
            _new_id(),
            lead_id,
            fin.cpf,
            birth_dt,
            fin.down_payment,
            fin.vehicle_model,
            fin.vehicle_year,
            fin.notes,
            fin.has_driver_license,
            fin.desired_monthly_payment,
            installment_count,
            fin.vehicle_id,
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
        extra_bits: list[str] = []
        if facts.get("trade_color"):
            extra_bits.append(f"cor {facts['trade_color']}")
        financing = facts.get("trade_has_financing")
        if financing is True:
            parcela = facts.get("trade_installment_value")
            restantes = facts.get("trade_installments_remaining")
            bit = "financiamento em aberto"
            if parcela is not None:
                bit += f" parcela {parcela}"
            if restantes is not None:
                bit += f" restam {restantes}"
            extra_bits.append(bit)
        elif financing is False:
            extra_bits.append("quitado")
        debts = facts.get("trade_has_debts")
        if debts is True:
            extra_bits.append(
                f"débitos: {facts.get('trade_debt_type')}"
                if facts.get("trade_debt_type")
                else "débitos pendentes"
            )
        elif debts is False:
            extra_bits.append("sem débitos")
        if facts.get("trade_price_expectation"):
            extra_bits.append(f"expectativa {facts['trade_price_expectation']}")
        extra = "; ".join(extra_bits)
        observations = facts.get("observations") or facts.get("notes")
        if extra:
            observations = f"{observations}; {extra}" if observations else extra
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
