"""Unit tests for closed-snapshot inbound coalesce (no live DB)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sdr.domain.inbound import ContentType, MediaFailureCode, MediaStatus
from sdr.domain.inbound_batch import (
    BATCH_JSON_KEY,
    BatchResult,
    InboundSegment,
    compose_inbound_turn,
    merge_turn_facts,
    select_snapshot_rows,
)
from sdr.application.coalesce import segment_from_row


def _row(
    *,
    mid: str,
    text: str,
    created_at: datetime,
    content_type: str = "TEXT",
    transcription: str | None = None,
    turn_facts: dict | None = None,
) -> dict:
    return {
        "id": mid,
        "contentType": content_type,
        "text": text,
        "transcription": transcription,
        "providerMessageId": f"prov-{mid}",
        "mediaMimeType": None,
        "createdAt": created_at,
        "turnFactsJson": turn_facts,
        "processingStatus": "PENDING",
    }


def test_snapshot_excludes_after_cutoff() -> None:
    t0 = datetime(2026, 8, 27, 12, 0, 0)
    cutoff = t0 + timedelta(seconds=5)
    rows = [
        _row(mid="a", text="Oi", created_at=t0),
        _row(mid="b", text="quero um Corolla", created_at=t0 + timedelta(seconds=1)),
        _row(mid="c", text="até 80 mil", created_at=t0 + timedelta(seconds=2)),
        _row(mid="late", text="depois", created_at=cutoff + timedelta(milliseconds=1)),
    ]
    snap = select_snapshot_rows(rows, cutoff=cutoff)
    assert [r["id"] for r in snap] == ["a", "b", "c"]


def test_out_of_order_arrival_sorted_by_created_at() -> None:
    t0 = datetime(2026, 8, 27, 12, 0, 0)
    cutoff = t0 + timedelta(minutes=1)
    # Arrived / listed out of order
    rows = [
        _row(mid="c", text="até 80 mil", created_at=t0 + timedelta(seconds=2)),
        _row(mid="a", text="Oi", created_at=t0),
        _row(mid="b", text="quero um Corolla", created_at=t0 + timedelta(seconds=1)),
    ]
    snap = select_snapshot_rows(rows, cutoff=cutoff)
    assert [r["id"] for r in snap] == ["a", "b", "c"]
    segs = [segment_from_row(r, order=i) for i, r in enumerate(snap)]
    turn = compose_inbound_turn(thread_id="conv", segments=segs, batch_id="batch-1")
    assert turn.effective_text == "Oi\nquero um Corolla\naté 80 mil"
    assert [s.message_id for s in turn.segments] == ["a", "b", "c"]


def test_compose_text_plus_audio_preserves_order() -> None:
    segs = [
        InboundSegment(
            message_id="1",
            content_type=ContentType.TEXT,
            text="Oi",
            order=0,
        ),
        InboundSegment(
            message_id="2",
            content_type=ContentType.AUDIO,
            text="quero um Corolla até oitenta mil",
            media_status=MediaStatus.OK,
            order=1,
        ),
    ]
    turn = compose_inbound_turn(thread_id="t", segments=segs, batch_id="b")
    assert turn.effective_text == "Oi\nquero um Corolla até oitenta mil"
    assert turn.content_type == ContentType.AUDIO
    assert len(turn.segments) == 2


def test_image_and_caption_same_segment() -> None:
    row = _row(
        mid="img1",
        text="foto da CG 160",
        created_at=datetime(2026, 8, 27, 12, 0, 0),
        content_type="IMAGE",
    )
    seg = segment_from_row(row, order=0)
    assert seg.content_type == ContentType.IMAGE
    assert seg.caption == "foto da CG 160"
    assert seg.resolved_text() == "foto da CG 160"
    turn = compose_inbound_turn(thread_id="t", segments=[seg], batch_id="b")
    assert turn.effective_text == "foto da CG 160"
    assert turn.content_type == ContentType.IMAGE
    assert len(turn.segments) == 1


def test_failed_audio_does_not_become_greeting_text() -> None:
    segs = [
        InboundSegment(
            message_id="1",
            content_type=ContentType.AUDIO,
            text=None,
            media_status=MediaStatus.FAILED,
            failure_code=MediaFailureCode.TRANSCRIPTION_FAILED,
            order=0,
        )
    ]
    turn = compose_inbound_turn(thread_id="t", segments=segs, batch_id="b")
    assert turn.is_media_failed
    assert turn.effective_text == ""
    assert turn.content_type == ContentType.AUDIO


def test_failed_document_keeps_document_content_type() -> None:
    segs = [
        InboundSegment(
            message_id="1",
            content_type=ContentType.DOCUMENT,
            text=None,
            media_status=MediaStatus.FAILED,
            failure_code=MediaFailureCode.EXTRACTION_FAILED,
            mime_type="application/pdf",
            order=0,
        )
    ]
    turn = compose_inbound_turn(thread_id="t", segments=segs, batch_id="b")
    assert turn.is_media_failed
    assert turn.content_type == ContentType.DOCUMENT
    assert turn.effective_text == ""


def test_merge_turn_facts_preserves_sdr_media() -> None:
    existing = {"_sdr_media": {"key": {"id": "x"}}, "noise": 1}
    patch = {
        BATCH_JSON_KEY: {
            "batch_id": "b1",
            "message_ids": ["m1"],
            "result": {"outbound_sent": False},
        }
    }
    merged = merge_turn_facts(existing, patch)
    assert merged["_sdr_media"]["key"]["id"] == "x"
    assert merged[BATCH_JSON_KEY]["batch_id"] == "b1"
    # Update result without dropping ids
    merged2 = merge_turn_facts(
        merged,
        {BATCH_JSON_KEY: {"result": {"outbound_sent": True, "outbound_texts": ["Oi"]}}},
    )
    assert merged2[BATCH_JSON_KEY]["batch_id"] == "b1"
    assert merged2[BATCH_JSON_KEY]["result"]["outbound_sent"] is True
    assert merged2[BATCH_JSON_KEY]["message_ids"] == ["m1"]


def test_merge_turn_facts_preserves_sdr_visual() -> None:
    existing = {
        "_sdr_media": {"key": {"id": "x"}},
        "_sdr_visual": {"resolution_source": "exact_media", "matched_vehicle_id": "veh-1"},
    }
    patch = {BATCH_JSON_KEY: {"batch_id": "b1", "status": "ERROR"}}
    merged = merge_turn_facts(existing, patch)
    assert merged["_sdr_visual"]["matched_vehicle_id"] == "veh-1"
    assert merged["_sdr_media"]["key"]["id"] == "x"


def test_retry_same_batch_ids_no_duplicate_when_outbound_sent() -> None:
    result = BatchResult(
        outbound_texts=["resposta única"],
        outbound_sent=True,
        outbound_provider_ids=["wa-1"],
        action="smalltalk",
    )
    assert result.to_dict()["outbound_sent"] is True
    # Rehydrate
    again = BatchResult.from_dict(result.to_dict())
    assert again.outbound_sent is True
    assert again.outbound_texts == ["resposta única"]


def test_message_after_cutoff_belongs_to_next_batch() -> None:
    t0 = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    cutoff = t0 + timedelta(seconds=10)
    batch1_candidates = [
        _row(mid="1", text="Oi", created_at=t0),
        _row(mid="2", text="quero um Corolla", created_at=t0 + timedelta(seconds=1)),
        _row(mid="3", text="até 80 mil", created_at=t0 + timedelta(seconds=2)),
    ]
    during_processing = _row(
        mid="4",
        text="e financiamento?",
        created_at=cutoff + timedelta(seconds=1),
    )
    first = select_snapshot_rows(batch1_candidates + [during_processing], cutoff=cutoff)
    assert [r["id"] for r in first] == ["1", "2", "3"]
    next_cutoff = cutoff + timedelta(seconds=30)
    second = select_snapshot_rows([during_processing], cutoff=next_cutoff)
    assert [r["id"] for r in second] == ["4"]


def test_two_conversations_independent_snapshots() -> None:
    t0 = datetime(2026, 8, 27, 12, 0, 0)
    cutoff = t0 + timedelta(seconds=5)
    conv_a = [
        _row(mid="a1", text="Oi", created_at=t0),
        _row(mid="a2", text="Corolla", created_at=t0 + timedelta(seconds=1)),
    ]
    conv_b = [
        _row(mid="b1", text="Olá", created_at=t0),
        _row(mid="b2", text="Civic", created_at=t0 + timedelta(seconds=1)),
    ]
    snap_a = select_snapshot_rows(conv_a, cutoff=cutoff)
    snap_b = select_snapshot_rows(conv_b, cutoff=cutoff)
    assert [r["id"] for r in snap_a] == ["a1", "a2"]
    assert [r["id"] for r in snap_b] == ["b1", "b2"]
    turn_a = compose_inbound_turn(
        thread_id="A",
        segments=[segment_from_row(r, order=i) for i, r in enumerate(snap_a)],
        batch_id="batch-A",
    )
    turn_b = compose_inbound_turn(
        thread_id="B",
        segments=[segment_from_row(r, order=i) for i, r in enumerate(snap_b)],
        batch_id="batch-B",
    )
    assert turn_a.effective_text == "Oi\nCorolla"
    assert turn_b.effective_text == "Olá\nCivic"
    assert turn_a.raw_message_ref["batch_id"] != turn_b.raw_message_ref["batch_id"]


def test_one_composed_turn_per_batch() -> None:
    t0 = datetime(2026, 8, 27, 12, 0, 0)
    rows = [
        _row(mid="1", text="Oi", created_at=t0),
        _row(mid="2", text="quero um Corolla", created_at=t0 + timedelta(seconds=1)),
        _row(mid="3", text="até 80 mil", created_at=t0 + timedelta(seconds=2)),
    ]
    snap = select_snapshot_rows(rows, cutoff=t0 + timedelta(seconds=10))
    turn = compose_inbound_turn(
        thread_id="conv",
        segments=[segment_from_row(r, order=i) for i, r in enumerate(snap)],
        batch_id="only-one",
    )
    # Single Understanding surface — one joined text, not three turns.
    assert turn.effective_text.count("\n") == 2
    assert turn.raw_message_ref["segment_count"] == 3
    assert turn.raw_message_ref["batch_id"] == "only-one"
