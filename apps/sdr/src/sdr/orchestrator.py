"""Conversation orchestrator — lock → debounce → media enrichment → process → persist."""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Protocol

import asyncpg
import redis.asyncio as redis

from sdr.application.coalesce import (
    batch_meta_from_seed,
    build_batch_from_claimed_rows,
    compose_turn_from_batch,
    is_retry_seed,
    quoted_from_row,
    segment_from_row,
    utc_now_naive,
)
from sdr.application.document_storage import DocumentStorageService, StoreDocumentRequest
from sdr.application.inbound_document import document_inbound_text, media_ref_from_row
from sdr.application.outbound_guard import (
    cancel_pending_automation,
    column_authorizes_outbound,
    human_assumed_live,
    ownership_revision_from_row,
    suppression_batch_result,
)
from sdr.application.process_turn import ProcessTurnResult, process_turn
from sdr.config import Settings, get_settings
from sdr.debounce import wait_until_quiet
from sdr.domain.commands import (
    RESET_MEMORY_CONFIRMATION_PT,
    is_reset_memory_command,
)
from sdr.domain.document_storage import STORAGE_STORED
from sdr.domain.inbound import (
    ContentType,
    InboundTurn,
    MediaFailureCode,
    MediaStatus,
    QuotedContext,
    make_audio_inbound,
    make_media_failed_inbound,
    make_text_inbound,
)
from sdr.domain.inbound_batch import (
    BatchResult,
    BatchStatus,
    dedupe_snapshot_rows,
    first_batch_partition,
    new_batch_id,
)
from sdr.domain.phone import normalize_phone
from sdr.domain.vendor_summary import is_placeholder_display_name
from sdr.domain.vehicle_reference import PresentedVehicleBinding, upsert_presented_binding
from sdr.domain.types import (
    Action,
    ActionPlan,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    TurnFacts,
)
from sdr.infrastructure.conversation_repository import (
    ConversationRepository,
    state_from_conversation_row,
)
from sdr.infrastructure.customer_repository import CustomerRepository
from sdr.infrastructure.document_repository import DocumentRepository
from sdr.infrastructure.evolution_client import EvolutionError
from sdr.infrastructure.lead_repository import LeadRepository
from sdr.infrastructure.storage_client import BotoObjectStore
from sdr.locks import phone_lock
from sdr.trace import make_tracer

logger = logging.getLogger(__name__)


def _presented_vehicle_payload(
    *,
    conversation_id: str,
    state: ConversationCanonicalState,
    media: Any,
    provider_message_id: str,
) -> dict[str, Any] | None:
    vehicle_id = getattr(media, "vehicle_id", None)
    if not vehicle_id:
        return None
    shown = list(getattr(state, "last_shown_vehicle_ids", None) or [])
    try:
        position = shown.index(str(vehicle_id))
    except ValueError:
        position = 0
    caption = getattr(media, "caption", "") or ""
    binding = PresentedVehicleBinding(
        conversation_id=conversation_id,
        provider_message_id=provider_message_id,
        vehicle_id=str(vehicle_id),
        presentation_type="CAPTION" if caption else "IMAGE",
        position=position,
        offer_set_id=getattr(state, "current_offer_set_id", None),
        media_url=getattr(media, "url", None),
        created_at=utc_now_naive().timestamp(),
    )
    upsert_presented_binding(state, binding)
    return binding.as_dict()


def _first_inbound_image_bytes(orchestrator: "Orchestrator", batch: Any) -> bytes | None:
    store = getattr(orchestrator, "_inbound_image_bytes", None) or {}
    for seg in getattr(batch, "segments", None) or []:
        mid = getattr(seg, "message_id", None)
        if not mid:
            continue
        data = store.pop(str(mid), None)
        if data:
            return data
    return None


class EvolutionSender(Protocol):
    async def send_text(self, phone: str, text: str, *, instance: str) -> None: ...

    async def send_media(
        self,
        phone: str,
        mediatype: str,
        url: str,
        mimetype: str,
        caption: str = "",
        *,
        instance: str,
    ) -> str | None: ...

    async def send_location(
        self,
        phone: str,
        *,
        latitude: float,
        longitude: float,
        name: str = "",
        address: str = "",
        instance: str,
    ) -> str | None: ...


class StubEvolutionSender:
    """Wave 1 stub — no network calls."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.sent_media: list[dict[str, str]] = []
        self.sent_locations: list[dict[str, Any]] = []

    async def send_text(self, phone: str, text: str, *, instance: str) -> None:
        self.sent.append((phone, text, instance))

    async def send_media(
        self,
        phone: str,
        mediatype: str,
        url: str,
        mimetype: str,
        caption: str = "",
        *,
        instance: str,
    ) -> str | None:
        self.sent_media.append(
            {
                "phone": phone,
                "mediatype": mediatype,
                "url": url,
                "mimetype": mimetype,
                "caption": caption,
                "instance": instance,
            }
        )
        return None

    async def send_location(
        self,
        phone: str,
        *,
        latitude: float,
        longitude: float,
        name: str = "",
        address: str = "",
        instance: str,
    ) -> str | None:
        self.sent_locations.append(
            {
                "phone": phone,
                "latitude": latitude,
                "longitude": longitude,
                "name": name,
                "address": address,
                "instance": instance,
            }
        )
        return None


async def default_understand(
    text: str,
    state: ConversationCanonicalState,
) -> TurnFacts:
    """Wire understanding extractor (heuristic or OpenAI per config)."""
    from sdr.context_builder import ConversationContextBuilder
    from sdr.understanding.extractor import extract_turn_facts

    linked = state.facts.get("crm_linked_vehicles")
    titles = (
        [part.strip() for part in str(linked).split(",") if part.strip()]
        if linked
        else None
    )
    summary = ConversationContextBuilder().build_understanding_summary(
        state,
        linked_vehicle_titles=titles,
    )
    return await extract_turn_facts(text, summary)


class Orchestrator:
    def __init__(
        self,
        pool: asyncpg.Pool,
        redis_client: redis.Redis | None,
        *,
        settings: Settings | None = None,
        understand=default_understand,
        evolution: EvolutionSender | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.pool = pool
        self.redis = redis_client
        self.understand = understand
        self.evolution: EvolutionSender = evolution or StubEvolutionSender()
        self.conversations = ConversationRepository(pool)
        self.customers = CustomerRepository(pool)
        self.leads = LeadRepository(pool)
        self.documents = DocumentRepository(pool)
        self.document_storage = DocumentStorageService(
            object_store=BotoObjectStore(),
            documents=self.documents,
            messages=self.conversations,
            settings=self.settings,
        )
        self._inbound_image_bytes: dict[str, bytes] = {}

    async def _human_assumed(self, conversation_id: str) -> tuple[bool, int]:
        """Re-read Conversation.botStatus from the persisted column.

        Never use canonicalStateJson.lifecycle to authorize or suppress send.
        Overlay already reconciles loaded state; live re-read is the gate.
        """
        return await human_assumed_live(self.conversations, conversation_id)

    async def _save_canonical_state(
        self,
        conversation_id: str,
        state: ConversationCanonicalState,
    ) -> bool:
        """Write the worker snapshot only if live ownership still matches.

        ``save_canonical_state`` returns False on CAS miss (HUMAN_ACTIVE or
        stale ``ownershipRevision``). Mocks that return None still count as
        applied so older tests keep their no-op save.
        """
        save = getattr(self.conversations, "save_canonical_state", None)
        if save is None:
            return True
        applied = await save(conversation_id, state)
        return applied is not False

    async def _record_human_active_skip(
        self,
        batch,
        *,
        ownership_revision: int,
        outbound_texts: list[str] | None = None,
        outbound_provider_ids: list[str | None] | None = None,
        outbound_sent: bool = False,
    ) -> dict[str, Any]:
        await cancel_pending_automation(batch.conversation_id)
        payload = suppression_batch_result(
            ownership_revision=ownership_revision,
            outbound_texts=outbound_texts,
            outbound_sent=outbound_sent,
            outbound_provider_ids=outbound_provider_ids,
            processed_at=utc_now_naive().isoformat() + "Z",
        )
        status = "DONE" if outbound_sent else "SKIPPED:HUMAN_ACTIVE"
        await self.conversations.finalize_batch_messages(
            batch.message_ids,
            status=status[:64],
            batch_patch={
                "batch_id": batch.batch_id,
                "turn_id": batch.batch_id,
                "conversation_id": batch.conversation_id,
                "anchor_message_id": batch.anchor_message_id,
                "cutoff": batch.cutoff.isoformat() + "Z",
                "message_ids": batch.message_ids,
                "canonical_order": batch.message_ids,
                "status": "DONE" if outbound_sent else "SKIPPED",
                "result": payload,
            },
        )
        return payload

    async def _silenced_turn(
        self,
        batch,
        *,
        state: ConversationCanonicalState,
        ownership_revision: int,
        outbound_texts: list[str] | None = None,
        outbound_provider_ids: list[str | None] | None = None,
        outbound_sent: bool = False,
    ) -> ProcessTurnResult:
        await self._record_human_active_skip(
            batch,
            ownership_revision=ownership_revision,
            outbound_texts=outbound_texts,
            outbound_provider_ids=outbound_provider_ids,
            outbound_sent=outbound_sent,
        )
        return ProcessTurnResult(
            action_plan=ActionPlan(
                action=Action.NO_REPLY,
                reason_code="human_active",
            ),
            state=state,
            outbound_texts=list(outbound_texts or []),
            turn_facts=TurnFacts(),
            tool_results=[],
        )

    # ------------------------------------------------------------------
    # Audio enrichment
    # ------------------------------------------------------------------

    async def _transcribe_audio_row(
        self,
        message_id: str,
        *,
        media_ref: dict | None,
        mime_type: str | None,
    ) -> str | None:
        """Attempt to download and transcribe an audio message.

        Returns transcription text or None on failure.
        A failed attempt is logged but NEVER silently becomes a greeting.
        """
        if media_ref is None:
            logger.info(
                "audio message %s: no media_ref stored; cannot download",
                message_id,
            )
            return None

        try:
            # Download audio bytes via Evolution API.
            evolution_client = getattr(self.evolution, "_client", None)
            if evolution_client is None:
                logger.warning(
                    "audio message %s: evolution client not available for download",
                    message_id,
                )
                return None

            media_data = await evolution_client.download_media_base64(media_ref)
            audio_b64 = media_data.get("base64") or ""
            if not audio_b64:
                logger.warning("audio message %s: empty base64 from Evolution", message_id)
                return None

            audio_bytes = base64.b64decode(audio_b64)
            if not audio_bytes:
                return None

            from sdr.media.audio_transcriber import transcribe_audio

            mime = mime_type or media_data.get("mimetype") or None
            transcription = await transcribe_audio(audio_bytes, mime_type=mime)
            if transcription:
                await self.conversations.save_transcription(message_id, transcription)
                logger.info(
                    "audio message %s: transcribed %d chars",
                    message_id,
                    len(transcription),
                )
            return transcription or None
        except Exception:
            logger.exception("audio message %s: transcription failed", message_id)
            return None

    async def _download_media_bytes(
        self,
        message_id: str,
        *,
        media_ref: dict | None,
    ) -> tuple[bytes | None, str | None]:
        if media_ref is None:
            logger.info("media message %s: no media_ref stored; cannot download", message_id)
            return None, None
        try:
            evolution_client = getattr(self.evolution, "_client", None)
            if evolution_client is None:
                logger.warning(
                    "media message %s: evolution client not available for download",
                    message_id,
                )
                return None, None
            media_data = await evolution_client.download_media_base64(media_ref)
            raw_b64 = media_data.get("base64") or ""
            if not raw_b64:
                logger.warning("media message %s: empty base64 from Evolution", message_id)
                return None, None
            data = base64.b64decode(raw_b64)
            mime = media_data.get("mimetype")
            return (data or None), (str(mime) if mime else None)
        except Exception:
            logger.exception("media message %s: download failed", message_id)
            return None, None

    async def _enrich_document_row(
        self,
        *,
        message_id: str,
        row: asyncpg.Record,
        caption: str,
    ) -> InboundTurn:
        """Download, extract, persist, then expose extracted text as InboundTurn."""
        media_ref = media_ref_from_row(row)
        mime_type = row.get("mediaMimeType")
        conversation_id = str(row.get("conversationId") or "")
        data, downloaded_mime = await self._download_media_bytes(
            message_id, media_ref=media_ref
        )
        mime = mime_type or downloaded_mime
        if not data:
            failure = (
                MediaFailureCode.NO_MEDIA_REF
                if media_ref is None
                else MediaFailureCode.DOWNLOAD_FAILED
            )
            return make_media_failed_inbound(
                thread_id=message_id,
                failure_code=failure,
                content_type=ContentType.DOCUMENT,
                provider_message_id=str(row.get("providerMessageId") or ""),
            )

        from sdr.media.processor import MediaContentType, process_media

        try:
            processed = await process_media(
                data,
                content_type=MediaContentType.DOCUMENT,
                mime_type=mime,
            )
        except Exception:
            logger.exception("document message %s: extraction failed", message_id)
            processed = None

        extracted = processed.extracted if processed is not None else None
        inbound_text = document_inbound_text(extracted, caption) or (caption or "").strip() or "documento"
        doc_type = "OTHER"
        if extracted is not None:
            doc_type = extracted.document_type or "OTHER"

        lead_id: str | None = None
        conv = None
        if conversation_id:
            conv = await self.conversations.get_by_id(conversation_id)
            ids = list((conv["activeLeadIds"] if conv else None) or [])
            lead_id = str(ids[0]) if ids else None

        storage_outcome = None
        try:
            storage_outcome = await self.document_storage.store_inbound_document(
                StoreDocumentRequest(
                    data=data,
                    mime_type=mime,
                    document_type=doc_type,
                    conversation_id=conversation_id or str(row.get("conversationId") or ""),
                    message_id=message_id,
                    provider_message_id=str(row.get("providerMessageId") or message_id),
                    lead_id=lead_id,
                    extracted_json=extracted.as_dict() if extracted is not None else None,
                    extraction_ok=extracted is not None,
                )
            )
        except Exception:
            logger.exception("document message %s: internal storage failed", message_id)

        if (
            storage_outcome is not None
            and storage_outcome.storage_status != STORAGE_STORED
            and lead_id
        ):
            try:
                await self.leads.notify_document_upload_failed(lead_id)
            except Exception:
                logger.exception("document message %s: upload-failed notify failed", message_id)

        # Flow safe fields from extracted document into the conversation state so
        # they appear in vendor summary and can be used by future turns.
        if extracted is not None and conversation_id:
            doc_fact_patch: dict[str, Any] = {}
            if extracted.cpf:
                doc_fact_patch["cpf"] = extracted.cpf
            if extracted.birth_date:
                doc_fact_patch["birth_date"] = extracted.birth_date
            if extracted.birth_city:
                doc_fact_patch["birth_city"] = extracted.birth_city
            if extracted.birth_state:
                doc_fact_patch["birth_state"] = extracted.birth_state
            if extracted.name:
                doc_fact_patch["name"] = extracted.name
            if doc_fact_patch:
                try:
                    await self.conversations.patch_canonical_facts(
                        conversation_id, doc_fact_patch
                    )
                except Exception:
                    logger.exception(
                        "document %s: failed to patch canonical facts", message_id
                    )

        inbound = InboundTurn(
            thread_id=message_id,
            content_type=ContentType.DOCUMENT,
            text=inbound_text,
            media_status=MediaStatus.OK,
            provider_message_id=str(row.get("providerMessageId") or ""),
            mime_type=mime,
        )
        if extracted is not None:
            inbound.raw_message_ref["document_extracted"] = extracted.as_dict()
        if storage_outcome is not None:
            inbound.raw_message_ref["storage_status"] = storage_outcome.storage_status
        return inbound

    # ------------------------------------------------------------------
    # Batch processing (closed snapshot after quiet window)
    # ------------------------------------------------------------------

    async def process_message_row(self, row: asyncpg.Record) -> ProcessTurnResult | None:
        """Process a work seed — closes a cutoff batch for that conversation."""
        return await self.process_batch_seed(row)

    async def process_batch_seed(self, seed: asyncpg.Record) -> ProcessTurnResult | None:
        phone = normalize_phone(seed["conversationPhone"] or "")
        instance = seed["conversationInstance"] or seed["instanceName"]
        conversation_id = str(seed["conversationId"])

        # Silence gates (HUMAN_ACTIVE / JULIA_DISABLED) run *after* claim so
        # PROTOCOL command ``/deletar`` can still reset a silenced thread.

        async def _run() -> ProcessTurnResult | None:
            # Quiet window first — do NOT hold the phone lock while waiting,
            # or a second poll (or concurrent seed) fails with lock contention
            # while debounce keeps extending.
            prior = await self.conversations.load_canonical_state(conversation_id)
            turn_count = prior.assistant_turn_count if prior is not None else 0
            quiet = await wait_until_quiet(
                self.redis,
                phone,
                settings=self.settings,
                assistant_turn_count=turn_count,
            )
            if self.redis is not None:
                async with phone_lock(self.redis, phone, settings=self.settings):
                    return await self._claim_and_run_batch(
                        seed=seed,
                        conversation_id=conversation_id,
                        phone=phone,
                        instance=instance,
                        quiet=quiet,
                    )
            return await self._claim_and_run_batch(
                seed=seed,
                conversation_id=conversation_id,
                phone=phone,
                instance=instance,
                quiet=quiet,
            )

        return await _run()

    async def _skip_seed_pending(self, seed: asyncpg.Record, *, reason: str) -> None:
        """Skip current PENDING snapshot for this conversation (pre-claim silence)."""
        conversation_id = str(seed["conversationId"])
        cutoff = utc_now_naive()
        pending = await self.conversations.list_pending_inbound_up_to(
            conversation_id, cutoff=cutoff
        )
        rows = pending or [seed]
        for row in rows:
            await self.conversations.mark_message_skipped(str(row["id"]), reason=reason)

    async def _claim_and_run_batch(
        self,
        *,
        seed: asyncpg.Record,
        conversation_id: str,
        phone: str,
        instance: str,
        quiet=None,
    ) -> ProcessTurnResult | None:
        retry = is_retry_seed(seed)
        batch_meta = batch_meta_from_seed(seed) if retry else None

        if retry and batch_meta:
            message_ids = [str(x) for x in (batch_meta.get("message_ids") or [])]
            if not message_ids:
                message_ids = [str(seed["id"])]
            result_meta = batch_meta.get("result") or {}
            if result_meta.get("outbound_sent") is True:
                # Idempotent: already answered — close as DONE, no duplicate send.
                await self.conversations.finalize_batch_messages(
                    message_ids,
                    status="DONE",
                    batch_patch={
                        **batch_meta,
                        "status": BatchStatus.DONE.value,
                        "result": result_meta,
                    },
                )
                return None
            claimed = await self.conversations.reclaim_error_batch(
                message_ids=message_ids,
                batch_meta=batch_meta,
            )
            cutoff = utc_now_naive()
            raw_cutoff = batch_meta.get("cutoff")
            if raw_cutoff:
                from sdr.domain.inbound_batch import parse_cutoff

                parsed = parse_cutoff(raw_cutoff)
                if parsed is not None:
                    cutoff = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
            batch_id = str(batch_meta.get("batch_id") or new_batch_id())
        else:
            cutoff = utc_now_naive()
            batch_id = new_batch_id()
            pending = await self.conversations.list_pending_inbound_up_to(
                conversation_id, cutoff=cutoff
            )
            pending = first_batch_partition(dedupe_snapshot_rows(pending))
            if not pending:
                return None
            claimed = await self.conversations.claim_inbound_batch(
                conversation_id=conversation_id,
                cutoff=cutoff,
                batch_id=batch_id,
                phone=phone,
                instance_name=instance,
                message_ids=[str(r["id"]) for r in pending],
            )

        if not claimed:
            return None

        segments = []
        for order, row in enumerate(claimed):
            seg = await self._enrich_row_to_segment(row, order=order)
            segments.append(seg)

        batch = build_batch_from_claimed_rows(
            claimed,
            conversation_id=conversation_id,
            phone=phone,
            instance_name=instance,
            cutoff=cutoff,
            batch_id=batch_id,
            segments=segments,
        )
        inbound = compose_turn_from_batch(batch)

        # PROTOCOL_DETERMINISTIC: exact ``/deletar`` wipes thread memory.
        if is_reset_memory_command(inbound.effective_text):
            return await self._handle_reset_memory_command(
                batch=batch,
                phone=phone,
                instance=instance,
            )

        conv_row = await self.conversations.get_by_id(conversation_id)
        bot_status = (
            conv_row["botStatus"]
            if conv_row is not None
            else seed.get("conversationBotStatus")
        )
        if not self.settings.julia_enabled:
            await self.conversations.finalize_batch_messages(
                batch.message_ids,
                status="SKIPPED:JULIA_DISABLED",
                batch_patch={
                    "batch_id": batch.batch_id,
                    "turn_id": batch.batch_id,
                    "anchor_message_id": batch.anchor_message_id,
                    "cutoff": batch.cutoff.isoformat() + "Z",
                    "message_ids": batch.message_ids,
                    "canonical_order": batch.message_ids,
                    "status": "SKIPPED",
                    "result": BatchResult(
                        outbound_sent=False, action="no_reply", reason_code="julia_disabled"
                    ).to_dict(),
                },
            )
            return None
        if not column_authorizes_outbound(
            str(bot_status) if bot_status is not None else None
        ):
            await self._record_human_active_skip(
                batch,
                ownership_revision=ownership_revision_from_row(conv_row),
            )
            return None

        try:
            result = await self._run_batch_turn(
                batch=batch,
                inbound=inbound,
                phone=phone,
                instance=instance,
                quiet=quiet,
            )
            return result
        except Exception as exc:
            logger.exception(
                "batch %s failed conversation=%s", batch.batch_id, conversation_id
            )
            err_result = BatchResult(
                outbound_sent=False,
                error=f"{type(exc).__name__}: {exc}"[:500],
                processed_at=utc_now_naive().isoformat() + "Z",
            )
            await self.conversations.finalize_batch_messages(
                batch.message_ids,
                status="ERROR",
                batch_patch={
                    "batch_id": batch.batch_id,
                    "turn_id": batch.batch_id,
                    "conversation_id": conversation_id,
                    "anchor_message_id": batch.anchor_message_id,
                    "cutoff": cutoff.isoformat() + "Z",
                    "message_ids": batch.message_ids,
                    "canonical_order": batch.message_ids,
                    "status": BatchStatus.ERROR.value,
                    "result": err_result.to_dict(),
                },
            )
            raise

    async def _handle_reset_memory_command(
        self,
        *,
        batch,
        phone: str,
        instance: str,
    ) -> ProcessTurnResult:
        """Clear conversation memory for this phone/thread and confirm to customer."""
        fresh = await self.conversations.reset_conversation_memory(
            batch.conversation_id, phone=phone
        )
        if self.redis is not None:
            try:
                from sdr.debounce import DEBOUNCE_KEY_PREFIX

                await self.redis.delete(f"{DEBOUNCE_KEY_PREFIX}{phone}")
            except Exception:
                logger.exception("failed clearing debounce key after /deletar")

        # Memory wipe is the contract; confirmation delivery is best-effort.
        # A ReadTimeout / Evolution blip must not leave /deletar stuck in ERROR
        # (retries would re-enter this path forever while the user sees silence).
        confirmation = RESET_MEMORY_CONFIRMATION_PT
        provider_id = None
        send_ok = False
        send = getattr(self.evolution, "send_text", None)
        if send is not None:
            try:
                maybe = await self.evolution.send_text(
                    phone, confirmation, instance=instance
                )
                if isinstance(maybe, str):
                    provider_id = maybe
                send_ok = True
            except Exception:
                logger.exception(
                    "reset_memory confirmation send failed conversation=%s batch=%s "
                    "(memory already wiped; finalizing DONE)",
                    batch.conversation_id,
                    batch.batch_id,
                )
        try:
            await self.conversations.insert_bot_outbound(
                conversation_id=batch.conversation_id,
                instance_name=instance,
                provider_message_id=provider_id or f"bot-reset-{batch.batch_id}",
                text=confirmation,
            )
        except Exception:
            logger.exception(
                "reset_memory outbound persist failed conversation=%s batch=%s",
                batch.conversation_id,
                batch.batch_id,
            )

        batch_result = BatchResult(
            outbound_texts=[confirmation] if send_ok else [],
            outbound_sent=send_ok,
            outbound_provider_ids=[provider_id] if provider_id else [],
            action="reset_memory",
            reason_code="command_deletar",
            processed_at=utc_now_naive().isoformat() + "Z",
            error=None if send_ok else "confirmation_send_failed",
        )
        await self.conversations.finalize_batch_messages(
            batch.message_ids,
            status="DONE",
            batch_patch={
                "batch_id": batch.batch_id,
                "turn_id": batch.batch_id,
                "conversation_id": batch.conversation_id,
                "anchor_message_id": batch.anchor_message_id,
                "cutoff": batch.cutoff.isoformat() + "Z",
                "message_ids": batch.message_ids,
                "canonical_order": batch.message_ids,
                "status": BatchStatus.DONE.value,
                "result": batch_result.to_dict(),
            },
        )
        logger.info(
            "reset_memory conversation=%s phone=%s batch=%s",
            batch.conversation_id,
            phone,
            batch.batch_id,
        )
        return ProcessTurnResult(
            action_plan=ActionPlan(
                action=Action.NO_REPLY,
                reason_code="command_deletar",
            ),
            state=fresh,
            outbound_texts=[confirmation],
            turn_facts=TurnFacts(),
            tool_results=[],
        )

    async def _enrich_row_to_segment(self, row: asyncpg.Record, *, order: int):
        content_type = str(row["contentType"] or "TEXT").upper()
        text = row["text"] or row["transcription"] or ""
        inbound = await self._build_inbound_turn(
            message_id=str(row["id"]),
            row=row,
            text=text,
            content_type=content_type,
        )
        quoted = await self._quoted_context_for_row(row, message_id=str(row["id"]))
        if quoted:
            inbound.quoted = [quoted]
        if inbound.media_status == MediaStatus.FAILED:
            seg = segment_from_row(
                row,
                order=order,
                text_override=None,
                media_status=MediaStatus.FAILED,
                failure_code=inbound.failure_code,
            )
        else:
            seg = segment_from_row(
                row,
                order=order,
                text_override=inbound.text,
                media_status=inbound.media_status,
            )
        if quoted:
            seg.quoted = quoted
        hint = inbound.raw_message_ref.get("vehicle_hint") if inbound.raw_message_ref else None
        if isinstance(hint, dict):
            seg.vehicle_hint = hint
        extracted = (
            inbound.raw_message_ref.get("document_extracted") if inbound.raw_message_ref else None
        )
        if isinstance(extracted, dict):
            seg.document_extracted = extracted
        return seg

    async def _quoted_context_for_row(
        self, row: asyncpg.Record, *, message_id: str
    ) -> QuotedContext | None:
        base = quoted_from_row(row)
        stanza_id = base.stanza_id if base else None
        quoted_text = base.quoted_text if base else None
        quoted_type = base.quoted_type if base else None
        if stanza_id:
            try:
                looked_up = await self.conversations.find_bot_message_text_by_provider_id(
                    stanza_id
                )
                if looked_up:
                    quoted_text = looked_up
            except Exception:
                logger.exception("message %s: lookup quoted stanza failed", message_id)
        if not stanza_id and not quoted_text:
            return None
        return QuotedContext(
            stanza_id=stanza_id,
            quoted_text=quoted_text,
            quoted_type=quoted_type,
        )

    async def _build_inbound_turn(
        self,
        *,
        message_id: str,
        row: asyncpg.Record,
        text: str,
        content_type: str,
    ) -> InboundTurn:
        """Resolve all modalities into a canonical InboundTurn.

        Audio path:
          - If transcription already stored → make_audio_inbound
          - If audio but no text → attempt download + transcription
          - If transcription fails → make_media_failed_inbound (NEVER '__MEDIA_FAILED__' text)

        Text / image path:
          - IMAGE uses caption on the same provider event (text field)
          - TEXT uses message text
        """
        if content_type == "AUDIO" and not text:
            turn_facts_raw = row.get("turnFactsJson")
            media_ref = None
            mime_type = row.get("mediaMimeType")
            if isinstance(turn_facts_raw, dict):
                media_ref = turn_facts_raw.get("_sdr_media")
            elif isinstance(turn_facts_raw, str):
                try:
                    parsed = json.loads(turn_facts_raw)
                    media_ref = parsed.get("_sdr_media")
                except Exception:
                    pass

            transcription = await self._transcribe_audio_row(
                message_id,
                media_ref=media_ref,
                mime_type=mime_type,
            )
            if transcription:
                return make_audio_inbound(
                    thread_id=message_id,
                    transcription=transcription,
                    mime_type=mime_type,
                    provider_message_id=str(row.get("providerMessageId") or ""),
                )
            failure_code = (
                MediaFailureCode.NO_MEDIA_REF if media_ref is None
                else MediaFailureCode.TRANSCRIPTION_FAILED
            )
            return make_media_failed_inbound(
                thread_id=message_id,
                failure_code=failure_code,
                content_type=ContentType.AUDIO,
                provider_message_id=str(row.get("providerMessageId") or ""),
            )

        if content_type == "AUDIO" and text:
            return make_audio_inbound(
                thread_id=message_id,
                transcription=text,
                mime_type=row.get("mediaMimeType"),
                provider_message_id=str(row.get("providerMessageId") or ""),
            )

        if content_type == "IMAGE":
            caption = (text or "").strip()
            media_ref = None
            turn_facts_raw = row.get("turnFactsJson")
            parsed_facts: dict = {}
            if isinstance(turn_facts_raw, dict):
                parsed_facts = turn_facts_raw
                media_ref = turn_facts_raw.get("_sdr_media")
            elif isinstance(turn_facts_raw, str):
                try:
                    parsed_facts = json.loads(turn_facts_raw)
                    media_ref = parsed_facts.get("_sdr_media")
                except Exception:
                    parsed_facts = {}

            precomputed = parsed_facts.get("_sdr_visual")
            img_data = None
            img_mime = row.get("mediaMimeType")
            already = isinstance(precomputed, dict) and precomputed.get("resolution_source")
            if media_ref is not None and not already:
                img_data, downloaded_mime = await self._download_media_bytes(
                    message_id, media_ref=media_ref
                )
                img_mime = downloaded_mime or img_mime

            inbound = InboundTurn(
                thread_id=message_id,
                content_type=ContentType.IMAGE,
                text=caption or None,
                media_status=MediaStatus.OK if caption else MediaStatus.NONE,
                provider_message_id=str(row.get("providerMessageId") or ""),
                mime_type=img_mime,
            )
            if already:
                inbound.raw_message_ref["visual_resolution"] = precomputed
            if img_data:
                inbound.raw_message_ref["_image_byte_size"] = len(img_data)
                self._inbound_image_bytes[message_id] = img_data
            return inbound

        if content_type == "DOCUMENT":
            return await self._enrich_document_row(
                message_id=message_id,
                row=row,
                caption=text,
            )

        inbound = make_text_inbound(
            thread_id=message_id,
            text=text,
            provider_message_id=str(row.get("providerMessageId") or ""),
        )
        return inbound

    async def _run_batch_turn(
        self,
        *,
        batch,
        inbound: InboundTurn,
        phone: str,
        instance: str,
        quiet=None,
    ) -> ProcessTurnResult:
        conversation_id = batch.conversation_id
        conv = await self.conversations.get_by_id(conversation_id)
        if conv is None:
            await self.conversations.finalize_batch_messages(
                batch.message_ids,
                status=f"SKIPPED:NO_CONVERSATION"[:64],
                batch_patch={
                    "batch_id": batch.batch_id,
                    "status": "SKIPPED",
                    "message_ids": batch.message_ids,
                },
            )
            raise RuntimeError(f"conversation {conversation_id} missing")

        state = state_from_conversation_row(conv)
        if not state.customer.phone:
            state.customer = CustomerState(phone=phone, name=state.customer.name)

        existing_customer = await self.customers.find_by_phone(phone)
        if existing_customer is not None:
            existing_name = str(existing_customer["name"] or "").strip()
            if is_placeholder_display_name(state.customer.name) and not is_placeholder_display_name(
                existing_name
            ):
                state.customer.name = existing_name

        # Live column only. Overlay already applied column over JSON on load;
        # stale JSON HUMAN_ACTIVE must not silence when the column is AI.
        assumed, revision = await self._human_assumed(conversation_id)
        if assumed:
            return await self._silenced_turn(
                batch,
                state=state,
                ownership_revision=revision or int(state.ownership_revision or 0),
            )

        tracer = make_tracer(thread_id=conversation_id, message_id=batch.anchor_message_id)
        with tracer:
            if hasattr(tracer, "batch"):
                tracer.batch(
                    batch_id=batch.batch_id,
                    cutoff=batch.cutoff.isoformat() + "Z",
                    candidate_ids=batch.message_ids,
                    included_ids=batch.message_ids,
                    anchor_message_id=batch.anchor_message_id,
                    composed_text=inbound.effective_text[:200],
                    segments=[
                        {
                            "message_id": s.message_id,
                            "content_type": s.content_type.value,
                            "order": s.order,
                        }
                        for s in batch.segments
                    ],
                    close_reason=getattr(quiet, "close_reason", None),
                    has_media=bool((inbound.raw_message_ref or {}).get("has_media")),
                    has_document=bool((inbound.raw_message_ref or {}).get("has_document")),
                    has_reply=bool(inbound.quoted)
                    or bool((inbound.raw_message_ref or {}).get("has_reply")),
                    runtime_call_count=1,
                    worker_id=(self.settings.sdr_worker_id or "").strip() or str(os.getpid()),
                    message_count=len(batch.message_ids),
                )
            tracer.inbound(
                content_type=inbound.content_type.value,
                text=inbound.text[:80] if inbound.text else None,
                from_me=False,
                media_status=inbound.media_status.value,
                failure_code=inbound.failure_code.value if inbound.failure_code else None,
            )

            linked_titles = await self.leads.list_linked_vehicle_titles(
                list(state.active_lead_ids or [])
            )

            # Inject recent conversation turns into Understanding when using the
            # default production path. Injected understand functions (tests/replay)
            # manage their own context and are used as-is.
            if self.understand is default_understand:
                _recent = await self.conversations.list_recent_turns(
                    conversation_id,
                    limit=5,
                    exclude_message_ids=batch.message_ids,
                )

                async def _understand_with_history(
                    text: str,
                    _state: ConversationCanonicalState,
                    *,
                    _recent_turns: list[dict] = _recent,
                ) -> TurnFacts:
                    from sdr.context_builder import ConversationContextBuilder
                    from sdr.understanding.extractor import extract_turn_facts

                    linked = _state.facts.get("crm_linked_vehicles")
                    titles = (
                        [p.strip() for p in str(linked).split(",") if p.strip()]
                        if linked
                        else None
                    )
                    summary = ConversationContextBuilder().build_understanding_summary(
                        _state,
                        linked_vehicle_titles=titles,
                        recent_turns=_recent_turns,
                    )
                    return await extract_turn_facts(text, summary)

                _understand_fn = _understand_with_history
            else:
                _understand_fn = self.understand

            assumed, revision = await self._human_assumed(conversation_id)
            if assumed:
                return await self._silenced_turn(
                    batch, state=state, ownership_revision=revision
                )

            result = await process_turn(
                state=state,
                inbound=inbound,
                understand=_understand_fn,
                pool=self.pool,
                linked_vehicle_titles=linked_titles or None,
                image_bytes=_first_inbound_image_bytes(self, batch),
            )

            vis = (inbound.raw_message_ref or {}).get("visual_resolution") or result.state.last_visual_resolution or {}
            if vis:
                image_ids = [
                    str(getattr(seg, "message_id", "") or "")
                    for seg in (getattr(batch, "segments", None) or [])
                    if str(getattr(getattr(seg, "content_type", None), "value", getattr(seg, "content_type", ""))).upper()
                    == "IMAGE"
                    and getattr(seg, "message_id", None)
                ]
                persist_ids = [mid for mid in image_ids if mid] or list(batch.message_ids)
                try:
                    await self.conversations.merge_message_turn_facts(
                        persist_ids,
                        {"_sdr_visual": vis},
                    )
                except Exception:
                    logger.exception("persist _sdr_visual failed conversation=%s", conversation_id)
            if vis and hasattr(tracer, "visual"):
                tracer.visual(
                    resolution_source=str(vis.get("resolution_source") or "") or None,
                    confidence=vis.get("confidence"),
                    candidate_vehicle_ids=list(vis.get("candidate_vehicle_ids") or []),
                    matched_vehicle_id=vis.get("matched_vehicle_id"),
                    vision_attempted=bool(vis.get("vision_attempted")),
                    vision_calls=int(vis.get("vision_calls") or 0),
                    fallback_reason=vis.get("fallback_reason"),
                    ambiguity_reason=vis.get("ambiguity_reason"),
                )
            tracer.understanding(
                intent=result.turn_facts.intent.value,
                language=result.turn_facts.language,
                facts_keys=list(result.turn_facts.facts.keys()),
                signals=result.turn_facts.signals.as_dict(),
                confidence=result.turn_facts.confidence,
                path="llm" if (self.settings.openai_api_key or "").strip() else "heuristic",
            )
            tracer.merge(
                intent_before=state.intent.value,
                intent_after=result.state.intent.value,
                lifecycle_before=state.lifecycle.status.value,
                lifecycle_after=result.state.lifecycle.status.value,
                facts_count=len(result.state.facts),
                pending_interaction_before=state.pending_interaction.value,
                pending_interaction_after=result.state.pending_interaction.value,
                alternative_scope=result.state.alternative_scope.value,
                budget_status=result.state.budget_status.value,
            )
            tracer.decision(
                action=result.action_plan.action.value,
                reason_code=result.action_plan.reason_code,
                tool_calls=result.action_plan.tool_calls,
                ask_field=result.action_plan.ask_field,
                inventory_search_key=result.state.last_inventory_search_key,
                primary_action=getattr(result.action_plan, "primary_action", None),
                supporting_acts=list(getattr(result.action_plan, "supporting_acts", None) or []),
                forbidden_concurrent_actions=list(
                    getattr(result.action_plan, "forbidden_concurrent_actions", None) or []
                ),
                handoff_ready=bool(result.state.handoff_ready),
                profile_complete=bool(result.state.profile_complete),
                primary_vehicle_id=result.state.primary_vehicle_id,
                remaining_documents_asked=bool(
                    getattr(result.state, "remaining_documents_asked", False)
                ),
                enrichment_ask_count=int(getattr(result.state, "enrichment_ask_count", 0) or 0),
                primary_vehicle_label=(
                    (getattr(result.action_plan, "qualification_trace", None) or {}).get(
                        "primary_vehicle_label"
                    )
                ),
                vehicle_label_source=(
                    (getattr(result.action_plan, "qualification_trace", None) or {}).get(
                        "vehicle_label_source"
                    )
                ),
                documents_received=list(
                    (getattr(result.action_plan, "qualification_trace", None) or {}).get(
                        "documents_received"
                    )
                    or []
                ),
                documents_missing=list(
                    (getattr(result.action_plan, "qualification_trace", None) or {}).get(
                        "documents_missing"
                    )
                    or []
                ),
                documents_deferred=list(
                    (getattr(result.action_plan, "qualification_trace", None) or {}).get(
                        "documents_deferred"
                    )
                    or []
                ),
                direct_question_detected=bool(
                    (getattr(result.action_plan, "qualification_trace", None) or {}).get(
                        "direct_question_detected"
                    )
                ),
                next_question=(
                    (getattr(result.action_plan, "qualification_trace", None) or {}).get(
                        "next_question"
                    )
                    or result.action_plan.ask_field
                ),
            )
            tracer.tools_executed(result.tool_results)
            if result.response_directive is not None:
                d = result.response_directive
                from sdr.understanding.response_composer import last_compose_meta

                compose_meta = last_compose_meta()
                dialogue_meta = compose_meta.get("dialogue") or {}
                tracer.composer_input(
                    action=d.action.value,
                    should_introduce=d.should_introduce,
                    intent=d.intent.value,
                    has_tool_results=bool(result.tool_results),
                    conversational_affordance=d.conversational_affordance.value,
                    budget_status=d.budget_status.value,
                    alternative_scope=d.alternative_scope.value,
                    dialogue_acts=(d.dialogue_plan or {}).get("acts"),
                    canonical_question=(d.dialogue_plan or {}).get("canonical_question"),
                    facts_to_acknowledge=(d.dialogue_plan or {}).get("facts_to_acknowledge"),
                    realized_acts=compose_meta.get("realized_acts") or dialogue_meta.get("realized_acts"),
                    dialogue_violations=dialogue_meta.get("violations"),
                    used_template_fallback=compose_meta.get("used_template_fallback"),
                    retries=compose_meta.get("retries"),
                )
            tracer.outbound(result.outbound_texts)
            if result.outbound_media and hasattr(tracer, "media_actions"):
                tracer.media_actions([m.to_dict() for m in result.outbound_media])

        assumed, revision = await self._human_assumed(conversation_id)
        if assumed:
            return await self._silenced_turn(
                batch, state=result.state, ownership_revision=revision
            )

        customer = await self.customers.upsert_by_phone(
            phone, name=result.state.customer.name
        )
        if not is_placeholder_display_name(result.state.customer.name):
            await self.leads.sync_names_for_customer(
                customer["id"], result.state.customer.name
            )
        first_inbound = None
        try:
            first_inbound = await self.conversations.fetch_first_customer_text(conversation_id)
        except Exception:
            logger.exception("first inbound lookup failed conversation=%s", conversation_id)
        if not first_inbound:
            first_inbound = (inbound.effective_text or "").strip() or None

        lead_id = result.state.active_lead_ids[0] if result.state.active_lead_ids else None
        commercial = result.action_plan.handoff or result.state.intent not in (
            BusinessIntent.UNKNOWN,
            BusinessIntent.SMALLTALK,
        )
        if lead_id is None and commercial:
            display_name = result.state.customer.name
            if is_placeholder_display_name(display_name):
                display_name = customer["name"]
            lead = await self.leads.create_from_state(
                result.state,
                customer_id=customer["id"],
                conversation_id=conversation_id,
                name=display_name,
                first_inbound=first_inbound,
            )
            if lead is not None:
                lead_id = lead["id"]
                result.state.active_lead_ids = [lead_id]
        if lead_id:
            await self.documents.attach_orphans_to_lead(conversation_id, lead_id)
            result.state.crm_revision = int(getattr(result.state, "crm_revision", 0) or 0) + 1
            try:
                if result.action_plan.handoff:
                    await self.leads.mark_qualified_for_handoff(
                        lead_id,
                        result.state,
                        first_inbound=first_inbound,
                        conversation_id=conversation_id,
                    )
                    from sdr.domain.ownership import confirm_vendor_dispatch

                    confirm_vendor_dispatch(result.state)
                else:
                    await self.leads.sync_from_state(
                        lead_id,
                        result.state,
                        qualify=False,
                        first_inbound=first_inbound,
                        conversation_id=conversation_id,
                    )
            except Exception:
                logger.exception(
                    "CRM persist failed lead=%s handoff=%s",
                    lead_id,
                    bool(result.action_plan.handoff),
                )

        # Persist pending_question before Evolution I/O so an overlapping inbound
        # (photos take seconds) does not re-ask the same field.
        # Do not write canonical state over a live HUMAN_ACTIVE assume.
        assumed, revision = await self._human_assumed(conversation_id)
        if assumed:
            return await self._silenced_turn(
                batch, state=result.state, ownership_revision=revision
            )

        planned_outbound = bool(
            result.outbound_texts
            or result.outbound_media
            or getattr(result, "outbound_location", None)
        )
        if planned_outbound:
            result.state.assistant_turn_count = state.assistant_turn_count + 1
        if not await self._save_canonical_state(conversation_id, result.state):
            assumed, revision = await self._human_assumed(conversation_id)
            if assumed:
                return await self._silenced_turn(
                    batch, state=result.state, ownership_revision=revision
                )

        # Pin, then media, then text. A later send failure must not retry the
        # pin — that duplicated location cards when sendText returned 400.
        # HUMAN_ACTIVE is re-checked immediately before every Evolution send.
        provider_ids: list[str | None] = []
        sent_texts: list[str] = []
        turns_sent = 0
        send_failures = 0
        suppressed_revision: int | None = None
        pin = getattr(result, "outbound_location", None)
        send_pin = getattr(self.evolution, "send_location", None)
        send_media = getattr(self.evolution, "send_media", None)
        directive = result.response_directive
        intro_then_media = bool(
            result.outbound_texts
            and result.outbound_media
            and (
                (directive and directive.should_introduce)
                or result.action_plan.action == Action.SHOW_OFFERS
            )
        )
        leading_texts = result.outbound_texts[:1] if intro_then_media else []
        trailing_texts = (
            result.outbound_texts[1:] if intro_then_media else list(result.outbound_texts)
        )

        async def _abort_if_human_assumed() -> bool:
            nonlocal suppressed_revision
            taken, rev = await self._human_assumed(conversation_id)
            if taken:
                suppressed_revision = rev
                return True
            return False

        async def _send_one_text(outbound: str) -> None:
            nonlocal turns_sent, send_failures
            if await _abort_if_human_assumed():
                return
            provider_id = None
            send = getattr(self.evolution, "send_text", None)
            try:
                if send is not None:
                    maybe = await self.evolution.send_text(
                        phone, outbound, instance=instance
                    )
                    if isinstance(maybe, str):
                        provider_id = maybe
            except Exception:
                send_failures += 1
                logger.exception(
                    "send_text failed conversation=%s batch=%s",
                    conversation_id,
                    batch.batch_id,
                )
                return
            await self.conversations.insert_bot_outbound(
                conversation_id=conversation_id,
                instance_name=instance,
                provider_message_id=provider_id or f"bot-batch-{batch.batch_id}-{turns_sent}",
                text=outbound,
            )
            provider_ids.append(provider_id)
            sent_texts.append(outbound)
            turns_sent += 1

        if isinstance(pin, dict) and pin.get("latitude") is not None and send_pin is not None:
            if not await _abort_if_human_assumed():
                provider_id = None
                try:
                    maybe = await send_pin(
                        phone,
                        latitude=float(pin["latitude"]),
                        longitude=float(pin["longitude"]),
                        name=str(pin.get("name") or "FacilCar"),
                        address=str(pin.get("address") or ""),
                        instance=instance,
                    )
                    if isinstance(maybe, str):
                        provider_id = maybe
                except Exception:
                    send_failures += 1
                    logger.exception(
                        "send_location pin failed conversation=%s batch=%s",
                        conversation_id,
                        batch.batch_id,
                    )
                else:
                    await self.conversations.insert_bot_outbound(
                        conversation_id=conversation_id,
                        instance_name=instance,
                        provider_message_id=provider_id
                        or f"bot-batch-{batch.batch_id}-location-{turns_sent}",
                        text=str(pin.get("address") or pin.get("name") or "location"),
                    )
                    provider_ids.append(provider_id)
                    turns_sent += 1

        for outbound in leading_texts:
            if suppressed_revision is not None:
                break
            await _send_one_text(outbound)

        for media in result.outbound_media:
            if await _abort_if_human_assumed():
                break
            provider_id = None
            try:
                if send_media is not None:
                    maybe = await self.evolution.send_media(
                        phone,
                        media.mediatype,
                        media.url,
                        media.mimetype,
                        media.caption,
                        instance=instance,
                    )
                    if isinstance(maybe, str):
                        provider_id = maybe
            except Exception:
                send_failures += 1
                logger.exception(
                    "send_media failed conversation=%s batch=%s",
                    conversation_id,
                    batch.batch_id,
                )
                continue
            provider_id_final = provider_id or f"bot-batch-{batch.batch_id}-media-{turns_sent}"
            presented = _presented_vehicle_payload(
                conversation_id=conversation_id,
                state=result.state,
                media=media,
                provider_message_id=provider_id_final,
            )
            await self.conversations.insert_bot_outbound(
                conversation_id=conversation_id,
                instance_name=instance,
                provider_message_id=provider_id_final,
                text=media.caption or media.url,
                content_type="IMAGE",
                presented_vehicle=presented,
            )
            provider_ids.append(provider_id)
            turns_sent += 1

        for outbound in trailing_texts:
            if suppressed_revision is not None:
                break
            await _send_one_text(outbound)

        if suppressed_revision is not None:
            # Confirmed outbound stays; do not clobber HUMAN_ACTIVE with result.state.
            return await self._silenced_turn(
                batch,
                state=result.state,
                ownership_revision=suppressed_revision,
                outbound_texts=sent_texts,
                outbound_provider_ids=provider_ids,
                outbound_sent=bool(sent_texts or provider_ids),
            )

        planned_outbound = (
            bool(isinstance(pin, dict) and pin.get("latitude") is not None)
            or bool(result.outbound_media)
            or bool(result.outbound_texts)
        )
        if planned_outbound and turns_sent == 0 and send_failures:
            raise EvolutionError("all outbound sends failed")

        assumed, revision = await self._human_assumed(conversation_id)
        if assumed:
            return await self._silenced_turn(
                batch,
                state=result.state,
                ownership_revision=revision,
                outbound_texts=sent_texts,
                outbound_provider_ids=provider_ids,
                outbound_sent=bool(sent_texts or provider_ids),
            )

        if not await self._save_canonical_state(conversation_id, result.state):
            assumed, revision = await self._human_assumed(conversation_id)
            if assumed:
                return await self._silenced_turn(
                    batch,
                    state=result.state,
                    ownership_revision=revision,
                    outbound_texts=sent_texts,
                    outbound_provider_ids=provider_ids,
                    outbound_sent=bool(sent_texts or provider_ids),
                )

        batch_result = BatchResult(
            outbound_texts=list(result.outbound_texts),
            outbound_sent=True,
            outbound_provider_ids=provider_ids,
            action=result.action_plan.action.value,
            reason_code=result.action_plan.reason_code,
            processed_at=utc_now_naive().isoformat() + "Z",
        )
        await self.conversations.finalize_batch_messages(
            batch.message_ids,
            status="DONE",
            batch_patch={
                "batch_id": batch.batch_id,
                "turn_id": batch.batch_id,
                "conversation_id": conversation_id,
                "anchor_message_id": batch.anchor_message_id,
                "cutoff": batch.cutoff.isoformat() + "Z",
                "message_ids": batch.message_ids,
                "canonical_order": batch.message_ids,
                "status": BatchStatus.DONE.value,
                "result": batch_result.to_dict(),
                "intent": result.turn_facts.intent.value,
                "language": result.turn_facts.language,
                "facts": result.turn_facts.facts,
                "signals": result.turn_facts.signals.as_dict(),
            },
        )
        return result
