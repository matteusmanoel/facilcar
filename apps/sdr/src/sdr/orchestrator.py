"""Conversation orchestrator — lock → debounce → media enrichment → process → persist."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Protocol

import asyncpg
import redis.asyncio as redis

from sdr.application.coalesce import (
    batch_meta_from_seed,
    build_batch_from_claimed_rows,
    compose_turn_from_batch,
    is_retry_seed,
    segment_from_row,
    utc_now_naive,
)
from sdr.application.inbound_document import document_inbound_text, media_ref_from_row
from sdr.application.process_turn import ProcessTurnResult, process_turn
from sdr.config import Settings, get_settings
from sdr.debounce import wait_until_quiet
from sdr.domain.commands import (
    RESET_MEMORY_CONFIRMATION_PT,
    is_reset_memory_command,
)
from sdr.domain.inbound import (
    ContentType,
    InboundTurn,
    MediaFailureCode,
    MediaStatus,
    make_audio_inbound,
    make_media_failed_inbound,
    make_text_inbound,
)
from sdr.domain.inbound_batch import (
    BatchResult,
    BatchStatus,
    new_batch_id,
)
from sdr.domain.phone import normalize_phone
from sdr.domain.vendor_summary import is_placeholder_display_name
from sdr.domain.types import (
    Action,
    ActionPlan,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    LifecycleStatus,
    TurnFacts,
)
from sdr.infrastructure.conversation_repository import (
    ConversationRepository,
    canonical_state_from_json,
)
from sdr.infrastructure.customer_repository import CustomerRepository
from sdr.infrastructure.document_repository import DocumentRepository
from sdr.infrastructure.evolution_client import EvolutionError
from sdr.infrastructure.lead_repository import LeadRepository
from sdr.infrastructure.storage_client import upload_document
from sdr.locks import phone_lock
from sdr.trace import make_tracer

logger = logging.getLogger(__name__)


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
        inbound_text = document_inbound_text(extracted, caption)
        doc_type = "OTHER"
        if extracted is not None:
            doc_type = extracted.document_type or "OTHER"

        lead_id: str | None = None
        customer_id: str | None = None
        conv = None
        if conversation_id:
            conv = await self.conversations.get_by_id(conversation_id)
            ids = list((conv["activeLeadIds"] if conv else None) or [])
            lead_id = str(ids[0]) if ids else None
            phone = str((conv["phone"] if conv else "") or "")
            if phone:
                customer = await self.customers.upsert_by_phone(phone)
                customer_id = str(customer["id"])

        try:
            uploaded = upload_document(
                data,
                customer_id=customer_id or conversation_id or "unknown",
                document_type=doc_type,
                mime_type=mime,
            )
            extraction_status = "DONE" if extracted is not None else "FAILED"
            await self.documents.insert(
                storage_key=uploaded.storage_key,
                document_type=doc_type,
                lead_id=lead_id,
                conversation_id=conversation_id or None,
                mime_type=mime,
                byte_size=uploaded.byte_size,
                extracted_json=extracted.as_dict() if extracted is not None else None,
                extraction_status=extraction_status,
            )
            if not uploaded.uploaded and lead_id:
                await self.leads.notify_document_upload_failed(lead_id)
        except Exception:
            logger.exception("document message %s: persist failed", message_id)

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

        if not inbound_text:
            return make_media_failed_inbound(
                thread_id=message_id,
                failure_code=MediaFailureCode.EXTRACTION_FAILED,
                content_type=ContentType.DOCUMENT,
                provider_message_id=str(row.get("providerMessageId") or ""),
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
            await wait_until_quiet(
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
                    )
            return await self._claim_and_run_batch(
                seed=seed,
                conversation_id=conversation_id,
                phone=phone,
                instance=instance,
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
            claimed = await self.conversations.claim_inbound_batch(
                conversation_id=conversation_id,
                cutoff=cutoff,
                batch_id=batch_id,
                phone=phone,
                instance_name=instance,
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
        if bot_status in (
            LifecycleStatus.HUMAN_ACTIVE.value,
            LifecycleStatus.HANDOFF_SENT.value,
        ):
            skip_reason = (
                "human_active"
                if bot_status == LifecycleStatus.HUMAN_ACTIVE.value
                else "handoff_sent"
            )
            await self.conversations.finalize_batch_messages(
                batch.message_ids,
                status=f"SKIPPED:{skip_reason.upper()}"[:64],
                batch_patch={
                    "batch_id": batch.batch_id,
                    "turn_id": batch.batch_id,
                    "anchor_message_id": batch.anchor_message_id,
                    "cutoff": batch.cutoff.isoformat() + "Z",
                    "message_ids": batch.message_ids,
                    "canonical_order": batch.message_ids,
                    "status": "SKIPPED",
                    "result": BatchResult(
                        outbound_sent=False, action="no_reply", reason_code=skip_reason
                    ).to_dict(),
                },
            )
            return None

        try:
            result = await self._run_batch_turn(
                batch=batch,
                inbound=inbound,
                phone=phone,
                instance=instance,
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
        if inbound.media_status == MediaStatus.FAILED:
            return segment_from_row(
                row,
                order=order,
                text_override=None,
                media_status=MediaStatus.FAILED,
                failure_code=inbound.failure_code,
            )
        return segment_from_row(
            row,
            order=order,
            text_override=inbound.text,
            media_status=inbound.media_status,
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
            # Attempt to identify vehicle brand/model/color from the image bytes.
            # The result is used to pre-fill search facts without requiring the
            # customer to re-type the vehicle name.
            media_ref = None
            turn_facts_raw = row.get("turnFactsJson")
            if isinstance(turn_facts_raw, dict):
                media_ref = turn_facts_raw.get("_sdr_media")
            elif isinstance(turn_facts_raw, str):
                try:
                    parsed = json.loads(turn_facts_raw)
                    media_ref = parsed.get("_sdr_media")
                except Exception:
                    pass

            vehicle_hint: dict | None = None
            if media_ref is not None:
                img_data, img_mime = await self._download_media_bytes(
                    message_id, media_ref=media_ref
                )
                if img_data:
                    from sdr.media.image_describer import extract_vehicle_intent_from_image

                    try:
                        hint = await extract_vehicle_intent_from_image(
                            img_data, mime_type=img_mime or row.get("mediaMimeType")
                        )
                        if (
                            hint
                            and hint.get("is_vehicle")
                            and float(hint.get("confidence") or 0) >= 0.5
                        ):
                            vehicle_hint = hint
                            logger.info(
                                "image %s: vehicle_hint brand=%s model=%s conf=%.2f",
                                message_id,
                                hint.get("brand"),
                                hint.get("model"),
                                hint.get("confidence"),
                            )
                    except Exception:
                        logger.exception("image %s: vehicle intent extraction failed", message_id)

            # Build enriched text: prefer caption; fall back to vehicle description.
            if not caption and vehicle_hint:
                parts = [
                    p for p in [
                        vehicle_hint.get("brand"),
                        vehicle_hint.get("model"),
                        vehicle_hint.get("color"),
                    ]
                    if p and isinstance(p, str) and p.strip()
                ]
                enriched_text = " ".join(parts) if parts else None
            else:
                enriched_text = caption or None

            turn_status = MediaStatus.OK if enriched_text else MediaStatus.NONE
            inbound = InboundTurn(
                thread_id=message_id,
                content_type=ContentType.IMAGE,
                text=enriched_text,
                media_status=turn_status,
                provider_message_id=str(row.get("providerMessageId") or ""),
                mime_type=row.get("mediaMimeType"),
            )
            if vehicle_hint:
                inbound.raw_message_ref["vehicle_hint"] = vehicle_hint
            return inbound

        if content_type == "DOCUMENT":
            return await self._enrich_document_row(
                message_id=message_id,
                row=row,
                caption=text,
            )

        # If the customer used WhatsApp reply on a bot vehicle card, inject
        # the quoted vehicle as context so Understanding does not lose the reference.
        quoted_vehicle_text: str | None = None
        turn_facts_raw_text = row.get("turnFactsJson")
        quoted_id: str | None = None
        if isinstance(turn_facts_raw_text, dict):
            quoted_id = turn_facts_raw_text.get("_sdr_quoted_id")
        elif isinstance(turn_facts_raw_text, str):
            try:
                quoted_id = json.loads(turn_facts_raw_text).get("_sdr_quoted_id")
            except Exception:
                pass
        if quoted_id:
            try:
                quoted_vehicle_text = (
                    await self.conversations.find_bot_message_text_by_provider_id(quoted_id)
                )
            except Exception:
                logger.exception(
                    "text message %s: lookup quoted vehicle failed", message_id
                )

        inbound = make_text_inbound(
            thread_id=message_id,
            text=text,
            provider_message_id=str(row.get("providerMessageId") or ""),
        )
        if quoted_vehicle_text:
            inbound.raw_message_ref["quoted_vehicle_text"] = quoted_vehicle_text
        return inbound

    async def _run_batch_turn(
        self,
        *,
        batch,
        inbound: InboundTurn,
        phone: str,
        instance: str,
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

        state = canonical_state_from_json(
            conv["canonicalStateJson"],
            thread_id=conv["id"],
            phone=phone,
            bot_status=conv["botStatus"],
            active_lead_ids=list(conv["activeLeadIds"] or []),
        )
        if not state.customer.phone:
            state.customer = CustomerState(phone=phone, name=state.customer.name)

        existing_customer = await self.customers.find_by_phone(phone)
        if existing_customer is not None:
            existing_name = str(existing_customer["name"] or "").strip()
            if is_placeholder_display_name(state.customer.name) and not is_placeholder_display_name(
                existing_name
            ):
                state.customer.name = existing_name

        if state.lifecycle.status in (
            LifecycleStatus.HUMAN_ACTIVE,
            LifecycleStatus.HANDOFF_SENT,
        ):
            skip_reason = (
                "human_active"
                if state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE
                else "handoff_sent"
            )
            await self.conversations.finalize_batch_messages(
                batch.message_ids,
                status=f"SKIPPED:{skip_reason.upper()}"[:64],
                batch_patch={
                    "batch_id": batch.batch_id,
                    "turn_id": batch.batch_id,
                    "anchor_message_id": batch.anchor_message_id,
                    "cutoff": batch.cutoff.isoformat() + "Z",
                    "message_ids": batch.message_ids,
                    "canonical_order": batch.message_ids,
                    "status": "SKIPPED",
                    "result": BatchResult(outbound_sent=False, action="no_reply").to_dict(),
                },
            )
            return ProcessTurnResult(
                action_plan=ActionPlan(
                    action=Action.NO_REPLY,
                    reason_code=skip_reason,
                ),
                state=state,
                outbound_texts=[],
                turn_facts=TurnFacts(),
                tool_results=[],
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

            result = await process_turn(
                state=state,
                inbound=inbound,
                understand=_understand_fn,
                pool=self.pool,
                linked_vehicle_titles=linked_titles or None,
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
            )
            tracer.tools_executed(result.tool_results)
            if result.response_directive is not None:
                d = result.response_directive
                tracer.composer_input(
                    action=d.action.value,
                    should_introduce=d.should_introduce,
                    intent=d.intent.value,
                    has_tool_results=bool(result.tool_results),
                    conversational_affordance=d.conversational_affordance.value,
                    budget_status=d.budget_status.value,
                    alternative_scope=d.alternative_scope.value,
                )
            tracer.outbound(result.outbound_texts)
            if result.outbound_media and hasattr(tracer, "media_actions"):
                tracer.media_actions([m.to_dict() for m in result.outbound_media])

        customer = await self.customers.upsert_by_phone(
            phone, name=result.state.customer.name
        )
        if not is_placeholder_display_name(result.state.customer.name):
            await self.leads.sync_names_for_customer(
                customer["id"], result.state.customer.name
            )
        if result.action_plan.handoff or result.state.intent not in (
            BusinessIntent.UNKNOWN,
            BusinessIntent.SMALLTALK,
        ):
            lead_id = result.state.active_lead_ids[0] if result.state.active_lead_ids else None
            if lead_id is None:
                display_name = result.state.customer.name
                if is_placeholder_display_name(display_name):
                    display_name = customer["name"]
                lead = await self.leads.create_from_state(
                    result.state,
                    customer_id=customer["id"],
                    conversation_id=conversation_id,
                    name=display_name,
                )
                if lead is not None:
                    lead_id = lead["id"]
                    result.state.active_lead_ids = [lead_id]
            if lead_id:
                await self.documents.attach_orphans_to_lead(conversation_id, lead_id)
            if lead_id and result.action_plan.handoff:
                try:
                    await self.leads.mark_qualified_for_handoff(lead_id, result.state)
                except Exception:
                    logger.exception(
                        "handoff persist failed lead=%s — still sending confirmation",
                        lead_id,
                    )

        # Persist pending_question before Evolution I/O so an overlapping inbound
        # (photos take seconds) does not re-ask the same field.
        planned_outbound = bool(
            result.outbound_texts
            or result.outbound_media
            or getattr(result, "outbound_location", None)
        )
        if planned_outbound:
            result.state.assistant_turn_count = state.assistant_turn_count + 1
        await self.conversations.save_canonical_state(conversation_id, result.state)

        # Pin, then media, then text. A later send failure must not retry the
        # pin — that duplicated location cards when sendText returned 400.
        provider_ids: list[str | None] = []
        turns_sent = 0
        send_failures = 0
        pin = getattr(result, "outbound_location", None)
        send_pin = getattr(self.evolution, "send_location", None)
        if isinstance(pin, dict) and pin.get("latitude") is not None and send_pin is not None:
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

        send_media = getattr(self.evolution, "send_media", None)
        directive = result.response_directive
        # Send leading text before photos when:
        # (a) introducing Julia on first contact, OR
        # (b) showing inventory results — so "Deixa eu dar uma olhadinha..." arrives
        #     before the vehicle images.
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

        async def _send_one_text(outbound: str) -> None:
            nonlocal turns_sent, send_failures
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
            turns_sent += 1

        for outbound in leading_texts:
            await _send_one_text(outbound)

        for media in result.outbound_media:
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
            await self.conversations.insert_bot_outbound(
                conversation_id=conversation_id,
                instance_name=instance,
                provider_message_id=provider_id
                or f"bot-batch-{batch.batch_id}-media-{turns_sent}",
                text=media.caption or media.url,
                content_type="IMAGE",
            )
            provider_ids.append(provider_id)
            turns_sent += 1

        for outbound in trailing_texts:
            await _send_one_text(outbound)

        planned_outbound = (
            bool(isinstance(pin, dict) and pin.get("latitude") is not None)
            or bool(result.outbound_media)
            or bool(result.outbound_texts)
        )
        if planned_outbound and turns_sent == 0 and send_failures:
            raise EvolutionError("all outbound sends failed")

        await self.conversations.save_canonical_state(conversation_id, result.state)

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
