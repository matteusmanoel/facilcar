"""Phase 11 replay matrix — follow-up clock jumps, scheduler, invariants.

Deterministic pytest uses understand_return stubs plus the in-memory
``sdr.replay.followup_harness`` double. Live LLM belongs to
``python -m sdr.gate_phase11`` after freeze (G1 x2, G2 x2 only).
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from sdr.domain.clock import GOLDEN_CLOCK_ISO, now_brt, set_clock
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


@pytest.mark.asyncio
async def test_g1_documents_tomorrow_14h() -> None:
    run = await run_scenario_detailed(_load("g1_documents_tomorrow_14h"))
    assert run.ok, "\n".join(run.errors)
    assert run.followup_sends == 1
    assert run.wait_state == "AWAITING_AFTER_FOLLOWUP"
    scheduled = [t.get("scheduledAt") for t in run.followup_tasks]
    assert any("2026-09-08T14:00:00-03:00" in str(item) for item in scheduled)
    assert run.followup_composer_calls == 1
    before = [t for t in run.turns if t.get("action") == "CLOCK_JUMP"]
    assert before
    assert before[0].get("followup_sends") == 0


@pytest.mark.asyncio
async def test_g2_spouse_without_time() -> None:
    run = await run_scenario_detailed(_load("g2_spouse_without_time"))
    assert run.ok, "\n".join(run.errors)
    assert run.followup_sends == 1
    first = run.turns[0]
    blob = " ".join(first.get("outbound") or []).lower()
    assert blob
    assert "vi que você sumiu" not in blob
    assert "urgente" not in blob


@pytest.mark.asyncio
async def test_g3_reply_before_due() -> None:
    run = await run_scenario_detailed(_load("g3_reply_before_due"))
    assert run.ok, "\n".join(run.errors)
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
    assert run.followup_sends == 0
    silenced = next(t for t in run.turns if t.get("inbound") == "Quero financiar a Strada sem entrada")
    assert silenced.get("outbound") == []
    assert silenced.get("llm_calls") == 0
    assert silenced.get("inbound_persisted") is True
    tick = [t for t in run.turns if t.get("action") in {"SCHEDULER_TICK", "FOLLOWUP_SEND"}][-1]
    assert tick.get("llm_calls") == 0
    assert not (tick.get("outbound") or [])


@pytest.mark.asyncio
async def test_g5_opt_out() -> None:
    run = await run_scenario_detailed(_load("g5_opt_out"))
    assert run.ok, "\n".join(run.errors)
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
    assert run.followup_sends == 1
    assert run.followup_composer_calls == 1
    assert len(run.followup_claims) == 1
    assert run.idempotency_keys == ["g6-two-workers"]


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
    assert run.followup_sends == 1
    mid = run.turns[1]
    assert mid.get("followup_sends") == 0
    assert mid.get("rescheduled")


@pytest.mark.asyncio
async def test_g8_vehicle_sold() -> None:
    run = await run_scenario_detailed(_load("g8_vehicle_sold"))
    assert run.ok, "\n".join(run.errors)
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
    assert run.followup_sends == 1
    assert run.wait_state == "DORMANT"
    assert run.obtained_terminal == "DORMANT"


@pytest.mark.asyncio
async def test_g10_post_handoff_before_human() -> None:
    run = await run_scenario_detailed(_load("g10_post_handoff_before_human"))
    assert run.ok, "\n".join(run.errors)
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


def test_clock_jump_does_not_sleep() -> None:
    set_clock(GOLDEN_CLOCK_ISO)
    start = now_brt()
    apply_clock_jump({"hours": 48})
    elapsed = now_brt() - start
    assert elapsed == timedelta(hours=48)
