"""Phase 11 replay matrix — follow-up clock jumps, scheduler, invariants.

Deterministic pytest uses understand_return stubs for intent/vehicle only.
G1–G10 run with ``execution_mode=production_policy`` (real Frente A policy,
scheduler, composer). ``followup_harness_double`` remains unit-test only.
Live LLM belongs to ``python -m sdr.gate_phase11`` after freeze.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from sdr.application.followup_runtime import EXECUTION_MODE_PRODUCTION
from sdr.domain.clock import GOLDEN_CLOCK_ISO, now_brt, set_clock
from sdr.domain.followup import PERMISSION_ASK_PT
from sdr.replay.followup_harness import (
    FollowUpHarness,
    apply_clock_jump,
    is_within_store_hours,
    next_open_window,
    pii_leaks,
    sanitize_artifact,
    two_workers_claim_once,
)
from sdr.replay.round_report import build_round_report
from sdr.replay.runner import run_scenario_detailed

_PHASE11 = Path(__file__).parent / "phase11"


def _load(stem: str) -> dict:
    return json.loads((_PHASE11 / f"{stem}.json").read_text(encoding="utf-8"))


def _assert_production_path(run) -> None:
    assert run.execution_mode == EXECUTION_MODE_PRODUCTION
    evidence = run.followup_evidence or {}
    assert evidence.get("policy_called") is True
    assert evidence.get("eligibility_evaluated") is True
    assert evidence.get("schedule_computed") is True
    assert evidence.get("task_persisted") is True
    assert evidence.get("scheduler_claimed") is True
    assert evidence.get("pre_send_checks_executed") is True
    assert evidence.get("execution_mode") == EXECUTION_MODE_PRODUCTION
    meta = getattr(run, "execution_meta", None) or {}
    if meta:
        assert meta.get("policy_mode") == EXECUTION_MODE_PRODUCTION
        assert meta.get("scheduler_hosted") is False
        assert "TEST_DOUBLE" not in json.dumps(meta)
    assert evidence.get("context_revision_loaded") is True
    assert evidence.get("context_revision_nonzero") is True
    assert int(evidence.get("context_revision") or 0) >= 1
    assert all(int(t.get("contextRevision") or 0) >= 1 for t in run.followup_tasks)
    if run.followup_sends or run.followup_claims:
        assert evidence.get("context_revision_checked_before_compose") is True
        assert evidence.get("context_revision_checked_before_send") is True


@pytest.mark.asyncio
async def test_g1_documents_tomorrow_14h() -> None:
    run = await run_scenario_detailed(_load("g1_documents_tomorrow_14h"))
    assert run.ok, "\n".join(run.errors)
    _assert_production_path(run)
    assert run.followup_sends == 1
    assert run.wait_state == "AWAITING_AFTER_FOLLOWUP"
    scheduled = [t.get("scheduledAt") for t in run.followup_tasks]
    assert any("2026-09-08T14:00:00" in str(item) for item in scheduled)
    assert run.followup_composer_calls == 1
    before = [t for t in run.turns if t.get("action") == "CLOCK_JUMP"]
    assert before
    assert before[0].get("followup_sends") == 0
    assert any(t.get("reason") == "DOCUMENTS_UNAVAILABLE" for t in run.followup_tasks)
    tick_blob = " ".join(
        " ".join(t.get("outbound") or [])
        for t in run.turns
        if str(t.get("action") or "") in {"SCHEDULER_TICK", "FOLLOWUP_SEND"}
        or str(t.get("event_kind") or "") == "scheduler_tick"
    ).lower()
    assert "ia enviar" not in tick_blob
    assert "prometeu" not in tick_blob
    meta = run.execution_meta or {}
    assert meta.get("policy_mode") == EXECUTION_MODE_PRODUCTION
    assert meta.get("scheduler_mode") == "controlled_tick"
    assert meta.get("persistence_mode") == "isolated"
    assert meta.get("scheduler_hosted") is False
    assert meta.get("llm_mode") == "stub"


@pytest.mark.asyncio
async def test_g2_spouse_without_time() -> None:
    run = await run_scenario_detailed(_load("g2_spouse_without_time"))
    assert run.ok, "\n".join(run.errors)
    _assert_production_path(run)
    assert run.followup_sends == 1
    first = run.turns[0]
    blob = " ".join(first.get("outbound") or [])
    assert PERMISSION_ASK_PT in blob
    assert "vi que você sumiu" not in blob.lower()
    assert "urgente" not in blob.lower()
    assert "combinou" not in blob.lower()
    scheduled = [str(t.get("scheduledAt") or "") for t in run.followup_tasks]
    assert any("2026-09-08T10:00:00" in item for item in scheduled)
    sources = {t.get("consentSource") for t in run.followup_tasks}
    assert "contextual_single_attempt" in sources
    assert all(t.get("consentSource") != "explicit_customer_time" for t in run.followup_tasks)
    evidence = run.followup_evidence or {}
    assert evidence.get("consent_source") == "contextual_single_attempt"
    assert evidence.get("customer_agreed_at") is None
    assert "2026-09-08T10:00:00" in str(evidence.get("fallback_resume_at") or "")


@pytest.mark.asyncio
async def test_g3_reply_before_due() -> None:
    run = await run_scenario_detailed(_load("g3_reply_before_due"))
    assert run.ok, "\n".join(run.errors)
    _assert_production_path(run)
    assert run.followup_sends == 0
    assert run.followup_cancels
    assert run.followup_cancels[0].get("cancelReason") == "CUSTOMER_REPLIED"
    reply = run.turns[1]
    assert reply.get("inbound")
    assert reply.get("outbound")
    assert reply.get("inbound_persisted") is True


@pytest.mark.asyncio
async def test_g4_human_assume() -> None:
    run = await run_scenario_detailed(_load("g4_human_assume"))
    assert run.ok, "\n".join(run.errors)
    _assert_production_path(run)
    assert run.followup_sends == 0
    silenced = next(t for t in run.turns if t.get("inbound") == "Quero financiar a Strada sem entrada")
    assert silenced.get("outbound") == []
    assert silenced.get("llm_calls") == 0
    tick = [t for t in run.turns if t.get("action") in {"SCHEDULER_TICK", "FOLLOWUP_SEND"}][-1]
    assert tick.get("llm_calls") == 0
    assert not (tick.get("outbound") or [])


@pytest.mark.asyncio
async def test_g5_opt_out() -> None:
    run = await run_scenario_detailed(_load("g5_opt_out"))
    assert run.ok, "\n".join(run.errors)
    _assert_production_path(run)
    assert run.followup_sends == 0
    opt = next(t for t in run.turns if "Não quero mais" in str(t.get("inbound") or ""))
    assert opt.get("outbound") == []
    assert opt.get("llm_calls") == 0
    assert run.followup_cancels
    assert run.followup_cancels[0].get("cancelReason") == "OPT_OUT"


@pytest.mark.asyncio
async def test_g6_two_workers() -> None:
    run = await run_scenario_detailed(_load("g6_two_workers"))
    assert run.ok, "\n".join(run.errors)
    _assert_production_path(run)
    assert run.followup_sends == 1
    assert run.followup_composer_calls == 1
    assert len(run.followup_claims) == 1
    keys = [k for k in run.idempotency_keys if k]
    assert len(set(keys)) == 1


def test_g6_two_workers_unit_cas() -> None:
    set_clock(GOLDEN_CLOCK_ISO)
    harness = FollowUpHarness(scenario_name="g6-unit", thread_id="t-g6")
    harness.schedule_from_turn(
        {
            "followup": {
                "schedule": True,
                "reason": "CUSTOMER_WILL_RETURN",
                "scheduled_at": "2026-09-07T10:00:00-03:00",
                "idempotency_key": "unit-g6",
                "vehicle_label": "Strada Freedom 1.4 2018",
            }
        }
    )
    stats = two_workers_claim_once(harness)
    assert stats["claims"] == 1
    assert stats["composer_calls"] == 1
    assert stats["sends"] == 1
    assert stats["idempotency_keys"] == {"unit-g6"}


@pytest.mark.asyncio
async def test_g7_after_hours() -> None:
    run = await run_scenario_detailed(_load("g7_after_hours"))
    assert run.ok, "\n".join(run.errors)
    _assert_production_path(run)
    assert run.followup_sends == 1
    scheduled = [str(t.get("scheduledAt") or "") for t in run.followup_tasks]
    assert any("2026-09-08T08:00:00" in item for item in scheduled)
    originals = [str(t.get("originalTemporalText") or "") for t in run.followup_tasks]
    assert any("19h" in item for item in originals)
    mid = run.turns[1]
    assert mid.get("followup_sends") == 0


@pytest.mark.asyncio
async def test_g8_vehicle_sold() -> None:
    run = await run_scenario_detailed(_load("g8_vehicle_sold"))
    assert run.ok, "\n".join(run.errors)
    _assert_production_path(run)
    assert run.followup_sends == 0
    assert run.wait_state == "DORMANT"
    assert run.followup_cancels
    assert run.followup_cancels[-1].get("cancelReason") == "VEHICLE_NO_LONGER_APPLICABLE"
    blob = " ".join(" ".join(t.get("outbound") or []) for t in run.turns).lower()
    assert "ainda temos" not in blob
    assert "alternativa" not in blob


@pytest.mark.asyncio
async def test_g9_dormant_after_followup() -> None:
    run = await run_scenario_detailed(_load("g9_dormant_after_followup"))
    assert run.ok, "\n".join(run.errors)
    _assert_production_path(run)
    assert run.followup_sends == 1
    assert run.wait_state == "DORMANT"
    assert run.obtained_terminal == "DORMANT"


@pytest.mark.asyncio
async def test_g10_post_handoff_before_human() -> None:
    run = await run_scenario_detailed(_load("g10_post_handoff_before_human"))
    assert run.ok, "\n".join(run.errors)
    _assert_production_path(run)
    actions = [str(t.get("action") or "").upper() for t in run.turns]
    assert actions.count("HANDOFF_VENDOR") == 1
    assert int(run.crm_handoff_count) == 1
    assert run.followup_sends == 0
    assert any(str(t.get("bot_status") or "") == "HUMAN_ACTIVE" for t in run.turns)

def test_e1_advance_hours() -> None:
    set_clock(GOLDEN_CLOCK_ISO)
    later = apply_clock_jump({"hours": 4})
    assert later.hour == 14
    assert later.date() == now_brt().date()


def test_e2_advance_day() -> None:
    set_clock(GOLDEN_CLOCK_ISO)
    later = apply_clock_jump({"days": 1})
    assert str(later.date()) == "2026-09-08"


def test_e3_weekend() -> None:
    set_clock("2026-09-12T10:00:00-03:00")
    assert now_brt().weekday() == 5
    sunday = apply_clock_jump("2026-09-13T10:00:00-03:00")
    assert sunday.weekday() == 6
    assert is_within_store_hours(sunday) is False
    nxt = next_open_window(sunday)
    assert nxt.weekday() == 0
    assert nxt.hour == 8


def test_e4_after_hours() -> None:
    set_clock("2026-09-07T19:00:00-03:00")
    assert is_within_store_hours() is False
    nxt = next_open_window()
    assert str(nxt.date()) == "2026-09-08"
    assert nxt.hour == 8


@pytest.mark.asyncio
async def test_e5_reply_before_due() -> None:
    await test_g3_reply_before_due()


@pytest.mark.asyncio
async def test_e6_human_before_due() -> None:
    await test_g4_human_assume()


@pytest.mark.asyncio
async def test_e7_one_send() -> None:
    run = await run_scenario_detailed(_load("g1_documents_tomorrow_14h"))
    assert run.followup_sends == 1
    assert run.followup_composer_calls == 1


@pytest.mark.asyncio
async def test_e8_dormant_transition() -> None:
    await test_g9_dormant_after_followup()


@pytest.mark.asyncio
async def test_e9_principal_event_executed() -> None:
    run = await run_scenario_detailed(_load("g1_documents_tomorrow_14h"))
    assert run.ok, "\n".join(run.errors)
    assert "SCENARIO: principal_event_not_executed" not in " ".join(run.errors)
    assert {e.get("type") for e in run.events_executed} >= {"clock_jump", "scheduler_tick"}


@pytest.mark.asyncio
async def test_e10_stable_counters() -> None:
    a = await run_scenario_detailed(_load("g6_two_workers"))
    b = await run_scenario_detailed(_load("g6_two_workers"))
    assert a.ok and b.ok
    assert a.followup_sends == b.followup_sends == 1
    assert a.followup_composer_calls == b.followup_composer_calls
    assert a.llm_calls == b.llm_calls
    report = build_round_report([a, b])
    assert report["followup_sends"] == 2
    assert report["clock_jumps"] == len(a.clock_jumps) + len(b.clock_jumps)


@pytest.mark.asyncio
async def test_e11_no_llm_when_cancelled() -> None:
    run = await run_scenario_detailed(_load("g4_human_assume"))
    assert run.ok, "\n".join(run.errors)
    for turn in run.turns:
        if str(turn.get("bot_status") or "") == "HUMAN_ACTIVE" and turn.get("inbound"):
            assert int(turn.get("llm_calls") or 0) == 0
        if str(turn.get("action") or "") in {"SCHEDULER_TICK", "FOLLOWUP_SEND"}:
            assert int(turn.get("llm_calls") or 0) == 0


@pytest.mark.asyncio
async def test_e12_artifact_without_pii() -> None:
    run = await run_scenario_detailed(_load("g1_documents_tomorrow_14h"))
    payload = sanitize_artifact(
        {
            "turns": run.turns,
            "traces": run.traces,
            "tasks": run.followup_tasks,
            "openai_api_key": "sk-should-not-leak",
            "cpf": "529.982.247-25",
        }
    )
    blob = json.dumps(payload, default=str)
    assert "sk-should-not-leak" not in blob
    assert "529.982.247-25" not in blob
    assert pii_leaks(blob) == []
    assert payload["openai_api_key"] == "[redacted]"
    assert payload["cpf"] == "[redacted]"


def test_gate_phase11_output_dir_is_gitignored() -> None:
    from sdr.gate_phase11 import OUT_DIR, ROOT

    assert OUT_DIR == ROOT / ".gate" / "phase11"
    gitignore = ROOT.joinpath(".gitignore").read_text(encoding="utf-8")
    assert ".gate/" in gitignore


def test_phase11_goldens_do_not_preseed_schedule() -> None:
    for path in _PHASE11.glob("g*.json"):
        if path.name == "g1_g10_mapping.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("execution_mode") == EXECUTION_MODE_PRODUCTION
        for turn in payload.get("turns") or []:
            followup = turn.get("followup")
            assert not (isinstance(followup, dict) and followup.get("schedule")), path.name
            facts = ((turn.get("understand_return") or {}).get("facts") or {})
            assert "pause_reason" not in facts, path.name
            assert "consent_level" not in facts, path.name
            assert "scheduled_at" not in facts, path.name
    set_clock(GOLDEN_CLOCK_ISO)
    start = now_brt()
    apply_clock_jump({"hours": 48})
    elapsed = now_brt() - start
    assert elapsed == timedelta(hours=48)
