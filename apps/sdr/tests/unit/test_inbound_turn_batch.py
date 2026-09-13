"""Phase 1 — InboundTurn batch contract (sanitized fixtures, no live I/O).

Fixture note: `tests/fixtures/sanitized_inbound_batch.yaml` is synthetic.
Relative intervals (including a 6s financing burst) are preserved; names,
phones, and IDs are fictional.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from sdr.application.coalesce import segment_from_row
from sdr.application.process_turn import process_turn
from sdr.config import Settings
from sdr.debounce import (
    QuietWindowResult,
    dynamic_debounce_ms,
    mark_activity,
    quiet_window_ms,
    wait_until_quiet,
)
from sdr.domain.inbound import QuotedContext, make_text_inbound
from sdr.domain.inbound_batch import (
    InboundSegment,
    compose_inbound_turn,
    dedupe_snapshot_rows,
    first_batch_partition,
    select_snapshot_rows,
)
from sdr.domain.inbound import ContentType, MediaStatus
from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState, TurnFacts
from sdr.locks import PhoneLock
from tests.fakes import FakeClock, FakeRedis

T0 = datetime(2026, 9, 7, 12, 0, 0)
SYN_PHONE_A = "5511900000001"
SYN_PHONE_B = "5511900000002"
SANITIZED_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "sanitized_inbound_batch.yaml"
)


def _settings() -> Settings:
    return Settings(
        sdr_debounce_ms=8000,
        sdr_debounce_max_ms=20000,
        sdr_worker_id="worker-test-1",
        julia_enabled=False,
    )


def _row(
    *,
    mid: str,
    text: str,
    created_at: datetime,
    content_type: str = "TEXT",
    provider_id: str | None = None,
    conversation_id: str = "syn-conv-a",
    turn_facts: dict | None = None,
    transcription: str | None = None,
) -> dict[str, Any]:
    return {
        "id": mid,
        "conversationId": conversation_id,
        "contentType": content_type,
        "text": text,
        "transcription": transcription,
        "providerMessageId": provider_id or f"syn-{mid}",
        "mediaMimeType": None,
        "createdAt": created_at,
        "turnFactsJson": turn_facts,
        "processingStatus": "PENDING",
        "direction": "INBOUND",
        "fromMe": False,
    }


def _load_sanitized_burst() -> list[dict[str, Any]]:
    data = yaml.safe_load(SANITIZED_FIXTURE.read_text(encoding="utf-8"))
    assert data["sanitized"] is True
    rows = []
    for event in data["events"]:
        offset = timedelta(milliseconds=int(event["t_offset_ms"]))
        rows.append(
            _row(
                mid=str(event["provider_message_id"]),
                text=event["text"],
                created_at=T0 + offset,
                content_type=event.get("content_type", "TEXT"),
                provider_id=event["provider_message_id"],
                conversation_id=data["conversation_id"],
            )
        )
    return rows


class InMemoryMessageStore:
    """SKIP LOCKED + unique provider-id semantics without Postgres."""

    def __init__(self) -> None:
        self._tx = asyncio.Lock()
        self.messages: dict[str, dict[str, Any]] = {}
        self.by_provider: dict[tuple[str, str], str] = {}
        self.wipes: list[str] = []
        self.runtime_calls: list[str] = []
        self._seq = 0

    def ingest(
        self,
        *,
        conversation_id: str,
        instance: str,
        provider_id: str,
        text: str,
        created_at: datetime,
        content_type: str = "TEXT",
        turn_facts: dict | None = None,
    ) -> str:
        key = (instance, provider_id)
        if key in self.by_provider:
            return "deduped"
        self._seq += 1
        mid = f"syn-db-{self._seq}"
        self.messages[mid] = _row(
            mid=mid,
            text=text,
            created_at=created_at,
            content_type=content_type,
            provider_id=provider_id,
            conversation_id=conversation_id,
            turn_facts=turn_facts,
        )
        self.by_provider[key] = mid
        return "created"

    def pending(self, conversation_id: str, cutoff: datetime) -> list[dict[str, Any]]:
        rows = [
            dict(m)
            for m in self.messages.values()
            if m["conversationId"] == conversation_id
            and m["processingStatus"] == "PENDING"
            and m["createdAt"] <= cutoff
        ]
        return select_snapshot_rows(rows, cutoff=cutoff)

    async def claim(
        self, conversation_id: str, cutoff: datetime, message_ids: list[str]
    ) -> list[dict[str, Any]]:
        async with self._tx:
            claimed: list[dict[str, Any]] = []
            for mid in message_ids:
                row = self.messages.get(mid)
                if row is None:
                    continue
                if row["conversationId"] != conversation_id:
                    continue
                if row["processingStatus"] != "PENDING":
                    continue
                if row["createdAt"] > cutoff:
                    continue
                row["processingStatus"] = "PROCESSING"
                claimed.append(dict(row))
            return claimed

    def finalize(self, message_ids: list[str], status: str) -> None:
        for mid in message_ids:
            if mid in self.messages:
                self.messages[mid]["processingStatus"] = status


async def _close_and_run(
    *,
    store: InMemoryMessageStore,
    redis: FakeRedis,
    clock: FakeClock,
    conversation_id: str,
    phone: str,
    settings: Settings,
    wipe_on_reset: bool = True,
) -> QuietWindowResult | None:
    pending_any = [
        m
        for m in store.messages.values()
        if m["conversationId"] == conversation_id and m["processingStatus"] in ("PENDING", "ERROR")
    ]
    if not pending_any:
        return None
    window = await wait_until_quiet(
        redis,
        phone,
        settings=settings,
        clock=clock,
        assistant_turn_count=0,
    )
    cutoff = T0 + timedelta(seconds=clock.monotonic())
    rows = dedupe_snapshot_rows(store.pending(conversation_id, cutoff))
    partition = first_batch_partition(rows)
    if not partition:
        return window
    lock = PhoneLock(redis, phone, settings=settings)
    if not await lock.acquire():
        return window
    try:
        claimed = await store.claim(
            conversation_id, cutoff, [str(r["id"]) for r in partition]
        )
        if not claimed:
            return window
        segs = [segment_from_row(r, order=i) for i, r in enumerate(claimed)]
        turn = compose_inbound_turn(
            thread_id=conversation_id, segments=segs, batch_id="batch-test"
        )
        texts = [str(r["text"] or "") for r in claimed]
        if wipe_on_reset and len(claimed) == 1 and texts[0].strip().casefold() == "/deletar":
            store.wipes.append(conversation_id)
        else:
            store.runtime_calls.append(turn.effective_text)
        store.finalize([str(r["id"]) for r in claimed], "DONE")
        return window
    finally:
        await lock.release()


# ---------------------------------------------------------------------------
# Quiet window policy
# ---------------------------------------------------------------------------


def test_quiet_window_is_8000ms_even_on_first_contact() -> None:
    settings = _settings()
    assert quiet_window_ms(settings=settings) == 8000
    assert dynamic_debounce_ms(0, settings=settings) == 8000
    assert dynamic_debounce_ms(3, settings=settings) == 8000
    assert dynamic_debounce_ms(0, settings=settings) == dynamic_debounce_ms(9, settings=settings)


def test_sanitized_fixture_is_synthetic_and_has_6s_gap() -> None:
    data = yaml.safe_load(SANITIZED_FIXTURE.read_text(encoding="utf-8"))
    assert data["sanitized"] is True
    assert data["phone"] == SYN_PHONE_A
    offsets = [int(e["t_offset_ms"]) for e in data["events"]]
    assert offsets == [0, 6000]


@pytest.mark.asyncio
async def test_case_a_financing_burst_is_one_turn() -> None:
    """t0 + t0+6s financing pair → one InboundTurn, one runtime call."""
    settings = _settings()
    clock = FakeClock()
    redis = FakeRedis()
    store = InMemoryMessageStore()
    rows = _load_sanitized_burst()
    first, second = rows

    store.ingest(
        conversation_id=first["conversationId"],
        instance="facilcar-sdr-test",
        provider_id=first["providerMessageId"],
        text=first["text"],
        created_at=first["createdAt"],
    )
    await mark_activity(redis, SYN_PHONE_A, settings=settings)

    async def arrive_second() -> None:
        store.ingest(
            conversation_id=second["conversationId"],
            instance="facilcar-sdr-test",
            provider_id=second["providerMessageId"],
            text=second["text"],
            created_at=second["createdAt"],
        )
        await mark_activity(redis, SYN_PHONE_A, settings=settings)

    clock.schedule(6.0, arrive_second)
    window = await _close_and_run(
        store=store,
        redis=redis,
        clock=clock,
        conversation_id=first["conversationId"],
        phone=SYN_PHONE_A,
        settings=settings,
    )
    assert window is not None
    assert window.close_reason == "quiet"
    assert len(store.runtime_calls) == 1
    joined = store.runtime_calls[0]
    assert "Compra financiada." in joined
    assert "Financia 100%?" in joined
    assert joined.count("\n") == 1


@pytest.mark.asyncio
async def test_case_b_three_bubbles_in_window_one_turn() -> None:
    settings = _settings()
    clock = FakeClock()
    redis = FakeRedis()
    store = InMemoryMessageStore()
    conv = "syn-conv-b"
    texts = ["Oi", "quero um sedan", "até 80 mil"]
    store.ingest(
        conversation_id=conv,
        instance="test",
        provider_id="syn-b-1",
        text=texts[0],
        created_at=T0,
    )
    await mark_activity(redis, SYN_PHONE_A, settings=settings)

    async def arrive_rest() -> None:
        store.ingest(
            conversation_id=conv,
            instance="test",
            provider_id="syn-b-2",
            text=texts[1],
            created_at=T0 + timedelta(seconds=2),
        )
        store.ingest(
            conversation_id=conv,
            instance="test",
            provider_id="syn-b-3",
            text=texts[2],
            created_at=T0 + timedelta(seconds=4),
        )
        await mark_activity(redis, SYN_PHONE_A, settings=settings)

    clock.schedule(2.0, arrive_rest)
    await _close_and_run(
        store=store, redis=redis, clock=clock, conversation_id=conv, phone=SYN_PHONE_A, settings=settings
    )
    assert store.runtime_calls == ["Oi\nquero um sedan\naté 80 mil"]


@pytest.mark.asyncio
async def test_case_c_max_window_splits_into_two_turns() -> None:
    settings = _settings()
    clock = FakeClock()
    redis = FakeRedis()
    store = InMemoryMessageStore()
    conv = "syn-conv-c"
    store.ingest(
        conversation_id=conv,
        instance="test",
        provider_id="syn-c-1",
        text="primeira",
        created_at=T0,
    )
    await mark_activity(redis, SYN_PHONE_A, settings=settings)

    async def keep_talking() -> None:
        await mark_activity(redis, SYN_PHONE_A, settings=settings)

    for t in (7.0, 14.0):
        clock.schedule(t, keep_talking)

    first = await _close_and_run(
        store=store, redis=redis, clock=clock, conversation_id=conv, phone=SYN_PHONE_A, settings=settings
    )
    assert first is not None
    assert first.close_reason == "max_wait"
    assert store.runtime_calls == ["primeira"]

    store.ingest(
        conversation_id=conv,
        instance="test",
        provider_id="syn-c-2",
        text="depois do teto",
        created_at=T0 + timedelta(seconds=21),
    )
    await mark_activity(redis, SYN_PHONE_A, settings=settings)
    second = await _close_and_run(
        store=store, redis=redis, clock=clock, conversation_id=conv, phone=SYN_PHONE_A, settings=settings
    )
    assert second is not None
    assert store.runtime_calls == ["primeira", "depois do teto"]


@pytest.mark.asyncio
async def test_case_d_two_contacts_are_not_grouped_or_blocked() -> None:
    settings = _settings()
    redis = FakeRedis()
    store = InMemoryMessageStore()
    store.ingest(
        conversation_id="syn-conv-d-a",
        instance="test",
        provider_id="syn-d-a",
        text="Civic",
        created_at=T0,
    )
    store.ingest(
        conversation_id="syn-conv-d-b",
        instance="test",
        provider_id="syn-d-b",
        text="Corolla",
        created_at=T0,
    )
    await mark_activity(redis, SYN_PHONE_A, settings=settings)
    await mark_activity(redis, SYN_PHONE_B, settings=settings)

    lock_a = PhoneLock(redis, SYN_PHONE_A, settings=settings)
    lock_b = PhoneLock(redis, SYN_PHONE_B, settings=settings)
    assert await lock_a.acquire()
    assert await lock_b.acquire()
    await lock_a.release()
    await lock_b.release()

    results = await asyncio.gather(
        _close_and_run(
            store=store,
            redis=redis,
            clock=FakeClock(),
            conversation_id="syn-conv-d-a",
            phone=SYN_PHONE_A,
            settings=settings,
        ),
        _close_and_run(
            store=store,
            redis=redis,
            clock=FakeClock(),
            conversation_id="syn-conv-d-b",
            phone=SYN_PHONE_B,
            settings=settings,
        ),
    )
    assert all(r is not None for r in results)
    assert set(store.runtime_calls) == {"Civic", "Corolla"}
    assert len(store.runtime_calls) == 2


def test_case_e_reply_keeps_author_text_and_quoted_id_separate() -> None:
    rows = [
        _row(
            mid="syn-e-1",
            text="Gostei dessa",
            created_at=T0,
            turn_facts={
                "_sdr_quoted_id": "syn-stanza-card-1",
                "_sdr_quoted": {
                    "stanzaId": "syn-stanza-card-1",
                    "quotedType": "conversation",
                    "quotedText": "Honda Civic 2020 — R$ 89.900",
                },
            },
        )
    ]
    segs = [segment_from_row(r, order=i) for i, r in enumerate(rows)]
    turn = compose_inbound_turn(thread_id="syn-conv-e", segments=segs, batch_id="b-e")
    assert turn.effective_text == "Gostei dessa"
    assert turn.quoted
    assert turn.quoted[0].stanza_id == "syn-stanza-card-1"
    assert turn.quoted[0].quoted_text is not None
    assert "Honda Civic" in turn.quoted[0].quoted_text
    assert "Honda Civic" not in turn.effective_text
    assert turn.raw_message_ref.get("has_reply") is True


def test_case_f_image_then_text_same_batch() -> None:
    rows = [
        _row(
            mid="syn-f-img",
            text="foto da frente",
            created_at=T0,
            content_type="IMAGE",
            turn_facts={"_sdr_media": {"key": {"id": "syn-media-1"}}},
        ),
        _row(
            mid="syn-f-txt",
            text="esse mesmo",
            created_at=T0 + timedelta(seconds=3),
        ),
    ]
    snap = select_snapshot_rows(rows, cutoff=T0 + timedelta(seconds=8))
    segs = [segment_from_row(r, order=i) for i, r in enumerate(snap)]
    turn = compose_inbound_turn(thread_id="syn-conv-f", segments=segs, batch_id="b-f")
    assert [s.content_type for s in turn.segments] == [ContentType.IMAGE, ContentType.TEXT]
    assert "foto da frente" in turn.effective_text
    assert "esse mesmo" in turn.effective_text
    assert turn.raw_message_ref.get("has_media") is True
    assert len(turn.segments) == 2


def test_case_f_document_then_text_same_batch() -> None:
    rows = [
        _row(
            mid="syn-f-doc",
            text="",
            created_at=T0,
            content_type="DOCUMENT",
            turn_facts={
                "_sdr_media": {"key": {"id": "syn-doc-1"}},
                "document_extracted": {"name": "Cliente Teste"},
            },
        ),
        _row(
            mid="syn-f-follow",
            text="segue o documento",
            created_at=T0 + timedelta(seconds=2),
        ),
    ]
    segs = [segment_from_row(r, order=i) for i, r in enumerate(rows)]
    turn = compose_inbound_turn(thread_id="syn-conv-f2", segments=segs, batch_id="b-f2")
    assert turn.segments[0].content_type == ContentType.DOCUMENT
    assert turn.raw_message_ref.get("has_document") is True
    assert "segue o documento" in turn.effective_text
    extracted = turn.raw_message_ref.get("document_extracted")
    assert isinstance(extracted, dict)
    assert extracted.get("name") == "Cliente Teste"


@pytest.mark.asyncio
async def test_case_g_duplicate_webhook_is_idempotent() -> None:
    store = InMemoryMessageStore()
    first = store.ingest(
        conversation_id="syn-conv-g",
        instance="test",
        provider_id="syn-dup-1",
        text="Oi",
        created_at=T0,
    )
    second = store.ingest(
        conversation_id="syn-conv-g",
        instance="test",
        provider_id="syn-dup-1",
        text="Oi",
        created_at=T0,
    )
    assert first == "created"
    assert second == "deduped"
    assert len(store.messages) == 1

    settings = _settings()
    clock = FakeClock()
    redis = FakeRedis()
    await mark_activity(redis, SYN_PHONE_A, settings=settings)
    await _close_and_run(
        store=store,
        redis=redis,
        clock=clock,
        conversation_id="syn-conv-g",
        phone=SYN_PHONE_A,
        settings=settings,
    )
    assert store.runtime_calls == ["Oi"]
    await _close_and_run(
        store=store,
        redis=redis,
        clock=clock,
        conversation_id="syn-conv-g",
        phone=SYN_PHONE_A,
        settings=settings,
    )
    assert store.runtime_calls == ["Oi"]


@pytest.mark.asyncio
async def test_case_h_two_workers_exclude_do_not_both_run() -> None:
    settings = _settings()
    clock = FakeClock()
    redis = FakeRedis()
    store = InMemoryMessageStore()
    store.ingest(
        conversation_id="syn-conv-h",
        instance="test",
        provider_id="syn-h-1",
        text="única",
        created_at=T0,
    )
    await mark_activity(redis, SYN_PHONE_A, settings=settings)

    started = asyncio.Event()
    release_first = asyncio.Event()

    async def slow_worker() -> None:
        window = await wait_until_quiet(
            redis, SYN_PHONE_A, settings=settings, clock=clock, assistant_turn_count=0
        )
        cutoff = T0 + timedelta(seconds=clock.monotonic())
        rows = first_batch_partition(dedupe_snapshot_rows(store.pending("syn-conv-h", cutoff)))
        lock = PhoneLock(redis, SYN_PHONE_A, settings=settings)
        assert await lock.acquire()
        started.set()
        try:
            claimed = await store.claim("syn-conv-h", cutoff, [str(r["id"]) for r in rows])
            await release_first.wait()
            if claimed:
                turn = compose_inbound_turn(
                    thread_id="syn-conv-h",
                    segments=[segment_from_row(r, order=i) for i, r in enumerate(claimed)],
                    batch_id="h1",
                )
                store.runtime_calls.append(turn.effective_text)
                store.finalize([str(r["id"]) for r in claimed], "DONE")
        finally:
            await lock.release()
        assert window.close_reason in {"quiet", "max_wait", "max_extensions"}

    async def racing_worker() -> str:
        await started.wait()
        lock = PhoneLock(redis, SYN_PHONE_A, settings=settings)
        acquired = await lock.acquire()
        if not acquired:
            return "lock_busy"
        try:
            cutoff = T0 + timedelta(seconds=clock.monotonic())
            rows = first_batch_partition(dedupe_snapshot_rows(store.pending("syn-conv-h", cutoff)))
            claimed = await store.claim("syn-conv-h", cutoff, [str(r["id"]) for r in rows])
            if claimed:
                store.runtime_calls.append("SHOULD_NOT_RUN")
                return "claimed"
            return "empty_claim"
        finally:
            await lock.release()

    task1 = asyncio.create_task(slow_worker())
    task2 = asyncio.create_task(racing_worker())
    await started.wait()
    race_result = await task2
    release_first.set()
    await task1
    assert race_result == "lock_busy"
    assert store.runtime_calls == ["única"]


@pytest.mark.asyncio
async def test_case_i_retry_after_claim_failure_is_recoverable_and_idempotent() -> None:
    store = InMemoryMessageStore()
    store.ingest(
        conversation_id="syn-conv-i",
        instance="test",
        provider_id="syn-i-1",
        text="retry me",
        created_at=T0,
    )
    cutoff = T0 + timedelta(seconds=8)
    rows = store.pending("syn-conv-i", cutoff)
    claimed = await store.claim("syn-conv-i", cutoff, [str(r["id"]) for r in rows])
    assert len(claimed) == 1
    store.finalize([str(claimed[0]["id"])], "ERROR")
    for row in store.messages.values():
        row["processingStatus"] = "PENDING"
        row["_sdr_batch"] = {"result": {"outbound_sent": False}}

    claimed2 = await store.claim("syn-conv-i", cutoff, [str(claimed[0]["id"])])
    assert len(claimed2) == 1
    store.runtime_calls.append("retry me")
    store.finalize([str(claimed2[0]["id"])], "DONE")
    for row in store.messages.values():
        row["result_outbound_sent"] = True

    # Already answered: reclaim must not produce a second runtime call.
    for row in store.messages.values():
        row["processingStatus"] = "ERROR"
        row["_sdr_batch"] = {"result": {"outbound_sent": True}}
    from sdr.application.coalesce import is_retry_seed

    seed = {
        "processingStatus": "ERROR",
        "turnFactsJson": {"_sdr_batch": {"result": {"outbound_sent": True}, "message_ids": [claimed[0]["id"]]}},
        "id": claimed[0]["id"],
    }
    assert is_retry_seed(seed) is False
    assert store.runtime_calls == ["retry me"]


def test_case_j_deletar_is_its_own_batch() -> None:
    rows = [
        _row(mid="syn-j-1", text="quero um Civic", created_at=T0),
        _row(mid="syn-j-2", text="/deletar", created_at=T0 + timedelta(seconds=1)),
        _row(mid="syn-j-3", text="recomeço comercial", created_at=T0 + timedelta(seconds=2)),
    ]
    first = first_batch_partition(rows)
    assert [r["id"] for r in first] == ["syn-j-1"]
    rest = [r for r in rows if r["id"] not in {x["id"] for x in first}]
    second = first_batch_partition(rest)
    assert [r["id"] for r in second] == ["syn-j-2"]
    rest2 = [r for r in rest if r["id"] not in {x["id"] for x in second}]
    third = first_batch_partition(rest2)
    assert [r["id"] for r in third] == ["syn-j-3"]


def test_case_j_deletar_first_does_not_absorb_later_commercial() -> None:
    rows = [
        _row(mid="syn-j-d1", text="/deletar", created_at=T0),
        _row(mid="syn-j-d2", text="quero financiar", created_at=T0 + timedelta(seconds=1)),
    ]
    assert [r["id"] for r in first_batch_partition(rows)] == ["syn-j-d1"]


def test_case_k_quoted_url_is_not_author_text() -> None:
    segs = [
        InboundSegment(
            message_id="syn-k-1",
            content_type=ContentType.TEXT,
            text="Gostei dessa",
            order=0,
            quoted=QuotedContext(
                stanza_id="syn-stanza-url-1",
                quoted_text="https://cdn.example.test/vehicle-card.jpg",
                quoted_type="conversation",
            ),
        )
    ]
    turn = compose_inbound_turn(thread_id="syn-conv-k", segments=segs, batch_id="b-k")
    assert turn.effective_text == "Gostei dessa"
    assert "https://" not in turn.effective_text
    assert turn.quoted[0].quoted_text is not None
    assert turn.quoted[0].quoted_text.startswith("https://cdn.example.test/")


@pytest.mark.asyncio
async def test_case_k_quoted_url_does_not_seed_desired_vehicle() -> None:
    inbound = make_text_inbound("syn-conv-k", "Gostei dessa")
    inbound.raw_message_ref["quoted_vehicle_text"] = "https://cdn.example.test/vehicle-card.jpg"
    inbound.quoted = [
        QuotedContext(
            stanza_id="syn-stanza-url-1",
            quoted_text="https://cdn.example.test/vehicle-card.jpg",
            quoted_type="conversation",
        )
    ]
    state = ConversationCanonicalState(
        thread_id="syn-conv-k",
        customer=CustomerState(phone=SYN_PHONE_A),
        assistant_turn_count=1,
    )

    async def understand(text: str, _state: ConversationCanonicalState) -> TurnFacts:
        assert "https://" not in text
        return TurnFacts(intent=BusinessIntent.SMALLTALK)

    from sdr.understanding import response_composer as rc

    original = rc.compose_response

    async def _template_only(s, p, tool_context=None, *, client=None):
        from sdr.understanding.response_composer import _template_compose, validate_bubbles

        return validate_bubbles(_template_compose(s, p, tool_context))

    rc.compose_response = _template_only
    try:
        result = await process_turn(state=state, inbound=inbound, understand=understand)
    finally:
        rc.compose_response = original

    desired = str(result.state.facts.get("desired_vehicle_text") or "")
    assert "https://" not in desired
    assert "cdn.example.test" not in desired


def test_timestamp_ties_sort_by_id() -> None:
    rows = [
        _row(mid="syn-z", text="depois", created_at=T0),
        _row(mid="syn-a", text="antes", created_at=T0),
    ]
    snap = select_snapshot_rows(rows, cutoff=T0 + timedelta(seconds=1))
    assert [r["id"] for r in snap] == ["syn-a", "syn-z"]


def test_dedupe_snapshot_rows_by_provider_and_id() -> None:
    rows = [
        _row(mid="syn-1", text="Oi", created_at=T0, provider_id="same"),
        _row(mid="syn-1", text="Oi", created_at=T0, provider_id="same"),
        _row(mid="syn-2", text="Oi", created_at=T0, provider_id="same"),
    ]
    out = dedupe_snapshot_rows(rows)
    assert [r["id"] for r in out] == ["syn-1"]


def test_compose_does_not_mix_quoted_into_author_join() -> None:
    segs = [
        InboundSegment(
            message_id="1",
            content_type=ContentType.TEXT,
            text="quero mais informações",
            order=0,
            quoted=QuotedContext(stanza_id="syn-q", quoted_text="Corolla XEi"),
        ),
        InboundSegment(
            message_id="2",
            content_type=ContentType.TEXT,
            text="pode ser branco",
            order=1,
        ),
    ]
    turn = compose_inbound_turn(thread_id="t", segments=segs, batch_id="b")
    assert turn.effective_text == "quero mais informações\npode ser branco"
    assert "Corolla XEi" not in turn.effective_text
    assert len(turn.quoted) == 1


def test_batch_trace_records_close_reason_and_flags() -> None:
    from sdr.trace import TurnTracer

    tracer = TurnTracer(thread_id="syn-conv-trace", message_id="syn-m1")
    tracer.batch(
        batch_id="b1",
        cutoff="2026-09-07T12:00:08Z",
        candidate_ids=["a", "b"],
        included_ids=["a", "b"],
        anchor_message_id="a",
        composed_text="Oi\nquero",
        close_reason="quiet",
        has_media=True,
        has_document=False,
        has_reply=True,
        runtime_call_count=1,
        worker_id="worker-test-1",
        message_count=2,
    )
    events = [e for e in tracer.stages if e.get("stage") == "BATCH"]
    assert len(events) == 1
    payload = events[0]
    assert payload["close_reason"] == "quiet"
    assert payload["has_media"] is True
    assert payload["has_reply"] is True
    assert payload["runtime_call_count"] == 1
    assert payload["worker_id"] == "worker-test-1"
    assert payload["message_count"] == 2
