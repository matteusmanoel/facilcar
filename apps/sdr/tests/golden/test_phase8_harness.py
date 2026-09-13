"""Harness-only checks for Phase 8 replay capabilities."""

from __future__ import annotations

from sdr.domain.inbound import ContentType
from sdr.replay.inbound import build_replay_inbound
from tests.golden.fixtures.seed_inventory_adapter import get_seed_by_id, search_seed
from tests.golden.fixtures.synthetic_media import load_image_fixture


def test_id_only_fox_is_not_found_by_model() -> None:
    empty = search_seed(model="Fox")
    assert empty["outcome"] == "SUCCESS_EMPTY"
    by_id = search_seed(vehicle_hint_id="VH-FOX-2014-001")
    assert by_id["outcome"] == "SUCCESS_FOUND"
    assert by_id["vehicles"][0]["id"] == "VH-FOX-2014-001"
    assert get_seed_by_id("VH-FOX-2014-001")["match_policy"] == "id_only"


def test_strada_search_returns_three_with_2018_third() -> None:
    result = search_seed(model="Strada")
    ids = [v["id"] for v in result["vehicles"]]
    assert ids == ["VH-STRADA-2021", "VH-STRADA-2017", "VH-STRADA-2018"]


def test_burst_events_form_one_inbound_turn() -> None:
    inbound, image_bytes, delays = build_replay_inbound(
        {
            "events": [
                {"content_type": "TEXT", "text": "Compra financiada.", "delay_ms": 0},
                {"content_type": "TEXT", "text": "Financia 100%?", "delay_ms": 1800},
            ]
        },
        thread_id="replay_test",
        turn_idx=0,
    )
    assert image_bytes is None
    assert delays == [0, 1800]
    assert inbound.effective_text == "Compra financiada.\nFinancia 100%?"
    assert inbound.raw_message_ref["segment_count"] == 2


def test_synthetic_fox_image_is_png() -> None:
    data = load_image_fixture("synthetic_fox")
    assert data is not None
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_quoted_stanza_is_not_author_text() -> None:
    inbound, _, _ = build_replay_inbound(
        {
            "events": [
                {
                    "content_type": "TEXT",
                    "text": "Gostei dessa opção. Financia 100%?",
                    "quoted_message_id": "replay-img-VH-STRADA-2018",
                }
            ]
        },
        thread_id="replay_test",
        turn_idx=1,
    )
    assert inbound.quoted[0].stanza_id == "replay-img-VH-STRADA-2018"
    assert "replay-img" not in inbound.effective_text
    assert inbound.content_type == ContentType.TEXT
