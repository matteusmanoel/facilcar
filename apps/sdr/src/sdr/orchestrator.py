"""Conversation orchestrator — lock → debounce → media enrichment → process → persist."""

from __future__ import annotations

import base64
import json
import logging
from typing import Protocol

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
from sdr.infrastructure.lead_repository import LeadRepository
from sdr.locks import phone_lock
from sdr.trace import make_tracer

logger = logging.getLogger(__name__)


class EvolutionSender(Protocol):
    async def send_text(self, phone: str, text: str, *, instance: str) -> None: ...


class StubEvolutionSender:
    """Wave 1 stub — no network calls."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send_text(self, phone: str, text: str, *, instance: str) -> None:
        self.sent.append((phone, text, instance))


async def default_understand(
    text: str,
    state: ConversationCanonicalState,
) -> TurnFacts:
    """Wire understanding extractor (heuristic or OpenAI per config)."""
    from sdr.understanding.extractor import extract_turn_facts

    # Richer state summary so the LLM has meaningful context.
    parts = [
        f"intent={state.intent.value}",
        f"lifecycle={state.lifecycle.status.value}",
    ]
    if state.customer.name:
        parts.append(f"customer_name={state.customer.name}")
    if state.language and state.language != "unknown":
        parts.append(f"language={state.language}")
    if state.facts:
        known = ", ".join(
            f"{k}={v}" for k, v in list(state.facts.items())[:8]
            if not k.startswith("_")
        )
        if known:
            parts.append(f"known_facts=[{known}]")
    summary = "; ".join(parts)
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
            await wait_until_quiet(self.redis, phone, settings=self.settings)
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
        if bot_status == LifecycleStatus.HUMAN_ACTIVE.value:
            await self.conversations.finalize_batch_messages(
                batch.message_ids,
                status="SKIPPED:HUMAN_ACTIVE",
                batch_patch={
                    "batch_id": batch.batch_id,
                    "turn_id": batch.batch_id,
                    "anchor_message_id": batch.anchor_message_id,
                    "cutoff": batch.cutoff.isoformat() + "Z",
                    "message_ids": batch.message_ids,
                    "canonical_order": batch.message_ids,
                    "status": "SKIPPED",
                    "result": BatchResult(
                        outbound_sent=False, action="no_reply", reason_code="human_active"
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

        confirmation = RESET_MEMORY_CONFIRMATION_PT
        provider_id = None
        send = getattr(self.evolution, "send_text", None)
        if send is not None:
            maybe = await self.evolution.send_text(
                phone, confirmation, instance=instance
            )
            if isinstance(maybe, str):
                provider_id = maybe
        await self.conversations.insert_bot_outbound(
            conversation_id=batch.conversation_id,
            instance_name=instance,
            provider_message_id=provider_id or f"bot-reset-{batch.batch_id}",
            text=confirmation,
        )

        batch_result = BatchResult(
            outbound_texts=[confirmation],
            outbound_sent=True,
            outbound_provider_ids=[provider_id],
            action="reset_memory",
            reason_code="command_deletar",
            processed_at=utc_now_naive().isoformat() + "Z",
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
            # Caption stays on the same canonical item as the image event.
            return InboundTurn(
                thread_id=message_id,
                content_type=ContentType.IMAGE,
                text=(text or "").strip() or None,
                media_status=MediaStatus.OK if (text or "").strip() else MediaStatus.NONE,
                provider_message_id=str(row.get("providerMessageId") or ""),
                mime_type=row.get("mediaMimeType"),
            )

        if content_type == "DOCUMENT":
            return InboundTurn(
                thread_id=message_id,
                content_type=ContentType.DOCUMENT,
                text=(text or "").strip() or None,
                media_status=MediaStatus.OK if (text or "").strip() else MediaStatus.NONE,
                provider_message_id=str(row.get("providerMessageId") or ""),
                mime_type=row.get("mediaMimeType"),
            )

        return make_text_inbound(
            thread_id=message_id,
            text=text,
            provider_message_id=str(row.get("providerMessageId") or ""),
        )

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

        if state.lifecycle.status == LifecycleStatus.HUMAN_ACTIVE:
            await self.conversations.finalize_batch_messages(
                batch.message_ids,
                status="SKIPPED:HUMAN_ACTIVE",
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
                    reason_code="human_active",
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

            result = await process_turn(
                state=state,
                inbound=inbound,
                understand=self.understand,
                pool=self.pool,
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

        customer = await self.customers.upsert_by_phone(
            phone, name=result.state.customer.name
        )
        if result.action_plan.handoff or result.state.intent not in (
            BusinessIntent.UNKNOWN,
            BusinessIntent.SMALLTALK,
        ):
            lead_id = result.state.active_lead_ids[0] if result.state.active_lead_ids else None
            if lead_id is None:
                lead = await self.leads.create_from_state(
                    result.state,
                    customer_id=customer["id"],
                    conversation_id=conversation_id,
                    name=result.state.customer.name or customer["name"],
                )
                if lead is not None:
                    lead_id = lead["id"]
                    result.state.active_lead_ids = [lead_id]
            if lead_id and result.action_plan.handoff:
                await self.leads.mark_qualified_for_handoff(lead_id, result.state)

        # Idempotent outbound: one send per batch_id.
        provider_ids: list[str | None] = []
        turns_sent = 0
        for outbound in result.outbound_texts:
            provider_id = None
            send = getattr(self.evolution, "send_text", None)
            if send is not None:
                maybe = await self.evolution.send_text(
                    phone, outbound, instance=instance
                )
                if isinstance(maybe, str):
                    provider_id = maybe
            await self.conversations.insert_bot_outbound(
                conversation_id=conversation_id,
                instance_name=instance,
                provider_message_id=provider_id or f"bot-batch-{batch.batch_id}-{turns_sent}",
                text=outbound,
            )
            provider_ids.append(provider_id)
            turns_sent += 1

        if turns_sent > 0:
            result.state.assistant_turn_count = state.assistant_turn_count + 1

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
