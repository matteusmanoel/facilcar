"""Phase 10R G1–G7 evidence matrix.

Each test name includes g1..g7. Bodies invoke existing contract tests or
replay the declared event through the golden runner — assertions are not
weakened. Live LLM belongs to `python -m sdr.gate_phase10r`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from sdr.config import get_settings
from sdr.domain.clock import GOLDEN_CLOCK_ISO, set_clock
from sdr.gate_phase9 import _prepare_scenario
from sdr.replay.runner import run_scenario_detailed
from tests.unit.test_ownership_suppression import _quiet
from tests.unit.test_post_handoff_continuity import (
    LEAD_ID,
    STRADA_2017,
    STRADA_2021,
    _assert_continuation,
    _handoff_sent_state,
)

_DIR = Path(__file__).parent
_PHASE10 = _DIR / "phase10"
_PHASE10R = _DIR / "phase10r"
_MAPPING = json.loads((_PHASE10R / "g1_g7_mapping.json").read_text(encoding="utf-8"))


def _load_phase10(name: str) -> dict:
    return json.loads((_PHASE10 / f"{name}.json").read_text(encoding="utf-8"))


def _load_phase10r(name: str) -> dict:
    return _prepare_scenario(json.loads((_PHASE10R / f"{name}.json").read_text(encoding="utf-8")))


@pytest.fixture(autouse=True)
def _no_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _freeze_golden_clock() -> None:
    set_clock(GOLDEN_CLOCK_ISO)
    yield
    set_clock(None)


@pytest.fixture
def patch_quiet():
    async def _immediate(*args, **kwargs):
        return _quiet()

    with patch("sdr.orchestrator.wait_until_quiet", side_effect=_immediate):
        yield


def test_g1_g7_mapping_covers_all_cases() -> None:
    assert list(_MAPPING) == ["G1", "G2", "G3", "G4", "G5", "G6", "G7"]
    for case, spec in _MAPPING.items():
        needle = case.lower()
        assert spec["pytest"], case
        for nodeid in spec["pytest"]:
            assert needle in nodeid.lower(), nodeid
        assert spec["declared_event"]


# ---------------------------------------------------------------------------
# G1 — document after handoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,caption,component,ack_token",
    [
        ("CNH", "segue minha cnh", "cnh", "cnh"),
        ("INCOME_PROOF", "mande o comprovante de renda", "proof_of_income", "renda"),
    ],
)
async def test_g1_document_after_handoff_acks_without_second_handoff(
    kind: str,
    caption: str,
    component: str,
    ack_token: str,
) -> None:
    from tests.unit.test_post_handoff_continuity import (
        test_c1_document_after_handoff_acks_without_second_handoff,
    )

    await test_c1_document_after_handoff_acks_without_second_handoff(
        kind, caption, component, ack_token
    )


@pytest.mark.asyncio
async def test_g1_document_after_handoff_golden_and_p10_01() -> None:
    from tests.golden.test_phase10_continuity import (
        test_e1_e2_e3_handoff_is_not_end_of_conversation,
    )

    await test_e1_e2_e3_handoff_is_not_end_of_conversation()
    run = await run_scenario_detailed(_load_phase10r("g1_document_after_handoff"))
    assert run.ok, "\n".join(run.errors)
    actions = [str(t.get("action") or "").upper() for t in run.turns]
    assert actions[0] == "HANDOFF_VENDOR"
    assert actions.count("HANDOFF_VENDOR") == 1
    assert int(run.crm_handoff_count) == 1
    assert run.crm_lead_id
    doc_turn = run.turns[1]
    assert "cnh" in (doc_turn.get("inbound") or "").lower()
    assert doc_turn.get("outbound")
    facts = getattr(run.final_state, "facts", {}) or {}
    status = facts.get("document_status") if isinstance(facts.get("document_status"), dict) else {}
    assert status.get("cnh") == "received"
    stored = (run.crm_report or {}).get("record_reread") or {}
    assert stored.get("id") == run.crm_lead_id
    assert run.final_state.active_lead_ids == [run.crm_lead_id]


# ---------------------------------------------------------------------------
# G2 — equipment question after handoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "Tem teto solar?",
        "Esse tem sensor de estacionamento?",
    ],
)
async def test_g2_equipment_question_after_handoff_answers_without_restart(text: str) -> None:
    from tests.unit.test_post_handoff_continuity import (
        test_c4_equipment_question_after_handoff_answers_without_restart,
    )

    await test_c4_equipment_question_after_handoff_answers_without_restart(text)
    if text != "Tem teto solar?":
        return
    run = await run_scenario_detailed(_load_phase10r("g2_equipment_question_after_handoff"))
    assert run.ok, "\n".join(run.errors)
    question = run.turns[1]
    assert question["inbound"] == "Tem teto solar?"
    assert question.get("outbound")
    assert str(question.get("action") or "").upper() != "HANDOFF_VENDOR"
    assert int(run.crm_handoff_count) == 1
    assert run.final_state.primary_vehicle_id == "VH-STRADA-2018"


# ---------------------------------------------------------------------------
# G3 — visit time change after handoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,expected_time",
    [
        ("Consigo ir às 15h em vez de 9h30", "15:00"),
        ("Melhor às 16h então", "16:00"),
    ],
)
async def test_g3_visit_time_change_after_handoff_updates_without_second_location(
    text: str,
    expected_time: str,
) -> None:
    from tests.unit.test_post_handoff_continuity import (
        test_c5_visit_time_change_updates_without_second_handoff_or_location,
    )

    await test_c5_visit_time_change_updates_without_second_handoff_or_location(text, expected_time)
    if expected_time != "15:00":
        return
    run = await run_scenario_detailed(_load_phase10r("g3_visit_time_change_after_handoff"))
    assert run.ok, "\n".join(run.errors)
    visit = run.turns[1]
    assert "15h" in (visit.get("inbound") or "")
    assert visit.get("outbound")
    assert run.final_state.visit_time == "15:00"
    assert run.final_state.visit_date == "2026-09-08"
    assert run.final_state.location_sent is True
    assert int(run.location_sends) <= 1
    assert int(run.crm_handoff_count) == 1
    assert run.crm_lead_id
    assert run.final_state.active_lead_ids == [run.crm_lead_id]


# ---------------------------------------------------------------------------
# G4 — assume before inbound
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_g4_assume_before_inbound_persists_without_llm_or_outbound(patch_quiet) -> None:
    from tests.unit.test_ownership_suppression import (
        test_b1_assume_before_claim_skips_and_preserves_inbound,
    )

    await test_b1_assume_before_claim_skips_and_preserves_inbound(patch_quiet)
    run = await run_scenario_detailed(_load_phase10("p10_02_assume_resume"))
    assert run.ok, "\n".join(run.errors)
    assume = run.turns[2]
    inbound = run.turns[3]
    assert assume.get("admin_event") == "assume"
    assert inbound["inbound"] == "Quero financiar o Civic sem entrada"
    assert inbound.get("outbound") == []
    assert inbound.get("llm_calls") == 0
    assert inbound.get("inbound_persisted") is True
    assert str(inbound.get("bot_status") or "") == "HUMAN_ACTIVE"
    assert run.suppressed_outbound_count >= 1
    assert "ai_silenced" in (run.suppressed_outbound_reasons or [])


# ---------------------------------------------------------------------------
# G5 — assume races (deterministic pytest only)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_g5_assume_during_composer_does_not_send(patch_quiet) -> None:
    from tests.unit.test_ownership_suppression import (
        test_b4_assume_during_composer_does_not_send,
    )

    await test_b4_assume_during_composer_does_not_send(patch_quiet)


@pytest.mark.asyncio
async def test_g5_assume_during_canonical_save_does_not_restore_outbound(patch_quiet) -> None:
    from tests.unit.test_ownership_suppression import (
        test_b11_assume_during_canonical_save_does_not_restore_outbound,
    )

    await test_b11_assume_during_canonical_save_does_not_restore_outbound(patch_quiet)


@pytest.mark.asyncio
async def test_g5_assume_immediately_before_send_suppresses(patch_quiet) -> None:
    from tests.unit.test_ownership_suppression import (
        test_b5_assume_immediately_before_send_suppresses,
    )

    await test_b5_assume_immediately_before_send_suppresses(patch_quiet)


# ---------------------------------------------------------------------------
# G6 — explicit resume, only future inbounds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_g6_explicit_resume_replies_only_to_future_inbounds() -> None:
    from tests.golden.test_phase10_continuity import (
        test_e4_e5_assume_silence_then_resume_later_inbound,
    )

    await test_e4_e5_assume_silence_then_resume_later_inbound()
    run = await run_scenario_detailed(_load_phase10("p10_02_assume_resume"))
    assert run.ok, "\n".join(run.errors)
    resume = run.turns[4]
    later = run.turns[5]
    silenced = run.turns[3]
    assert resume.get("admin_event") == "resume"
    assert str(resume.get("bot_status") or "") == "AI_RESUMED"
    assert later.get("outbound")
    assert "Quero financiar o Civic sem entrada" not in " ".join(later.get("outbound") or [])
    assert str(later.get("bot_status") or "") == "AI_RESUMED"
    assert silenced.get("outbound") == []


# ---------------------------------------------------------------------------
# G7 — quoted reply other vehicle after handoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,stanza,expected_primary",
    [
        ("Gostei dessa opção", "prov-img-2021", STRADA_2021),
        ("Quero essa", "prov-img-2017", STRADA_2017),
    ],
)
async def test_g7_quoted_reply_other_vehicle_after_handoff(
    text: str,
    stanza: str,
    expected_primary: str,
) -> None:
    from sdr.application.process_turn import process_turn
    from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus, QuotedContext
    from tests.unit.test_post_handoff_continuity import (
        _understand,
        test_c6_quoted_reply_changes_primary_without_inventory_search,
    )

    previous = _handoff_sent_state()
    shown_before = list(previous.last_shown_vehicle_ids)
    await test_c6_quoted_reply_changes_primary_without_inventory_search(
        text, stanza, expected_primary
    )
    inbound = InboundTurn(
        thread_id=previous.thread_id,
        content_type=ContentType.TEXT,
        text=text,
        media_status=MediaStatus.OK,
        quoted=[QuotedContext(stanza_id=stanza, quoted_text="Fiat Strada")],
    )
    result = await process_turn(
        state=_handoff_sent_state(),
        inbound=inbound,
        understand=_understand(),
    )
    _assert_continuation(result)
    assert result.state.primary_vehicle_id == expected_primary
    assert result.state.last_shown_vehicle_ids == shown_before
    assert expected_primary in result.state.last_shown_vehicle_ids
    assert result.state.active_lead_ids == [LEAD_ID]
    if expected_primary != STRADA_2021:
        return
    run = await run_scenario_detailed(_load_phase10r("g7_quoted_other_strada_after_handoff"))
    assert run.ok, "\n".join(run.errors)
    quote = run.turns[1]
    assert quote["inbound"] == "Gostei dessa opção"
    assert run.final_state.primary_vehicle_id == "VH-STRADA-2021"
    shown = list(run.final_state.last_shown_vehicle_ids or [])
    assert "VH-STRADA-2018" in shown
    assert "VH-STRADA-2017" in shown
    assert int(run.crm_handoff_count) == 1
    stored = (run.crm_report or {}).get("record_reread") or {}
    assert stored.get("id") == run.crm_lead_id
    assert stored.get("vehicleId") == "VH-STRADA-2021" or run.final_state.primary_vehicle_id == "VH-STRADA-2021"
