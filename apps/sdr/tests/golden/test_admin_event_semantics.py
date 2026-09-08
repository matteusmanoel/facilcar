"""Phase 10R Frente A — admin events are not Composer turns.

ADMIN_ASSUME / ADMIN_RESUME emit empty outbound by contract. empty_composer
must not treat them as failed customer replies, and must require the
ownership transition. Same check_scenario path for llm_real and pytest.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdr.replay.runner import ScenarioRunResult, run_scenario_detailed
from tests.golden.invariants import check_scenario

_PHASE10 = Path(__file__).parent / "phase10"


def _load(name: str) -> dict:
    return json.loads((_PHASE10 / f"{name}.json").read_text(encoding="utf-8"))


def _codes(violations) -> list[str]:
    return [v.invariant for v in violations]


def _fake_run(*, name: str, turns: list[dict], fallback_count: int = 0) -> ScenarioRunResult:
    return ScenarioRunResult(
        ok=True,
        errors=[],
        name=name,
        turns=turns,
        fallback_count=fallback_count,
        technical_status="TECHNICAL_PASS",
        obtained_terminal="HANDOFF_VENDOR",
    )


def _customer_turn(**overrides) -> dict:
    row = {
        "idx": 0,
        "inbound": "Tem o Civic?",
        "action": "ASK_INFO",
        "outbound": ["Sim, temos opções."],
        "event_kind": "customer_inbound",
        "composer_expected": True,
        "outbound_expected": True,
        "runtime_call_count": 1,
        "runtime_calls": 1,
        "bot_status": "HANDOFF_SENT",
        "ownership_revision": 0,
    }
    row.update(overrides)
    return row


def _admin_turn(*, idx: int, event: str, status: str, revision: int, **overrides) -> dict:
    action = f"ADMIN_{event.upper()}"
    row = {
        "idx": idx,
        "inbound": "",
        "admin_event": event,
        "action": action,
        "outbound": [],
        "event_kind": "admin_event",
        "composer_expected": False,
        "outbound_expected": False,
        "llm_calls": 0,
        "runtime_calls": 0,
        "runtime_call_count": 0,
        "bot_status": status,
        "ownership_revision": revision,
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_a1_admin_assume_empty_outbound_passes() -> None:
    scenario = _load("p10_02_assume_resume")
    run = await run_scenario_detailed(scenario)
    assert run.ok, "\n".join(run.errors)
    assume = run.turns[2]
    assert str(assume.get("action") or "").upper() == "ADMIN_ASSUME"
    assert assume.get("outbound") == []
    assert assume.get("event_kind") == "admin_event"
    assert assume.get("composer_expected") is False
    assert assume.get("outbound_expected") is False
    assert "SCENARIO: empty_composer" not in " ".join(run.errors)
    codes = _codes(check_scenario(scenario=scenario, result=run, llm_real=True))
    assert "SCENARIO: empty_composer" not in codes


@pytest.mark.asyncio
async def test_a2_admin_resume_empty_outbound_passes() -> None:
    scenario = _load("p10_02_assume_resume")
    run = await run_scenario_detailed(scenario)
    assert run.ok, "\n".join(run.errors)
    resume = run.turns[4]
    assert str(resume.get("action") or "").upper() == "ADMIN_RESUME"
    assert resume.get("outbound") == []
    assert resume.get("event_kind") == "admin_event"
    assert resume.get("composer_expected") is False
    assert resume.get("outbound_expected") is False
    assert "SCENARIO: empty_composer" not in " ".join(run.errors)
    codes = _codes(check_scenario(scenario=scenario, result=run, llm_real=True))
    assert "SCENARIO: empty_composer" not in codes


@pytest.mark.asyncio
async def test_a3_admin_events_require_ownership_transition() -> None:
    scenario = _load("p10_02_assume_resume")
    run = await run_scenario_detailed(scenario)
    assert run.ok, "\n".join(run.errors)

    assume = run.turns[2]
    previous = run.turns[1]
    assert str(assume.get("bot_status") or "") == "HUMAN_ACTIVE"
    assert int(assume.get("ownership_revision") or 0) > int(previous.get("ownership_revision") or 0)

    resume = run.turns[4]
    silenced = run.turns[3]
    assert str(resume.get("bot_status") or "") == "AI_RESUMED"
    assert int(resume.get("ownership_revision") or 0) > int(silenced.get("ownership_revision") or 0)

    broken = _fake_run(
        name="a3_no_transition",
        turns=[
            _customer_turn(idx=0, action="HANDOFF_VENDOR", outbound=["Encaminhei."]),
            _admin_turn(idx=1, event="assume", status="HANDOFF_SENT", revision=0),
            _admin_turn(idx=2, event="resume", status="HUMAN_ACTIVE", revision=0),
        ],
    )
    codes = _codes(check_scenario(scenario={"name": "a3_no_transition", "turns": [{}, {}, {}]}, result=broken))
    assert "SCENARIO: admin_ownership_transition" in codes
    assert "SCENARIO: empty_composer" not in codes


def test_a4_composer_expected_empty_outbound_fails_llm_real() -> None:
    scenario = {"name": "a4_empty_composer", "turns": [{"inbound": "Tem o Civic?"}]}
    fake = _fake_run(
        name="a4_empty_composer",
        turns=[_customer_turn(outbound=[], action="ASK_INFO")],
    )
    codes = _codes(check_scenario(scenario=scenario, result=fake, llm_real=True))
    assert "SCENARIO: empty_composer" in codes


def test_a5_direct_empty_customer_response_fails() -> None:
    scenario = {"name": "a5_empty_customer", "turns": [{"inbound": "Oi, quero um carro"}]}
    fake = _fake_run(
        name="a5_empty_customer",
        turns=[
            {
                "idx": 0,
                "inbound": "Oi, quero um carro",
                "action": "SMALLTALK",
                "outbound": [],
            }
        ],
    )
    codes = _codes(check_scenario(scenario=scenario, result=fake, llm_real=False))
    assert "SCENARIO: empty_composer" in codes


def test_a6_human_active_suppressed_inbound_requires_audit_reason() -> None:
    scenario = {"name": "a6_suppressed", "turns": [{"inbound": "Quero financiar"}]}
    with_reason = _fake_run(
        name="a6_suppressed",
        turns=[
            {
                "idx": 0,
                "inbound": "Quero financiar",
                "action": "NO_REPLY",
                "outbound": [],
                "event_kind": "suppressed",
                "composer_expected": False,
                "outbound_expected": False,
                "bot_status": "HUMAN_ACTIVE",
                "suppressed_reason": "ai_silenced",
                "ownership_revision": 1,
            }
        ],
    )
    assert _codes(check_scenario(scenario=scenario, result=with_reason)) == []

    human_active = _fake_run(
        name="a6_suppressed",
        turns=[{**with_reason.turns[0], "suppressed_reason": "human_active"}],
    )
    assert _codes(check_scenario(scenario=scenario, result=human_active)) == []

    missing = _fake_run(
        name="a6_suppressed",
        turns=[
            {
                "idx": 0,
                "inbound": "Quero financiar",
                "action": "NO_REPLY",
                "outbound": [],
                "bot_status": "HUMAN_ACTIVE",
                "ownership_revision": 1,
            }
        ],
    )
    codes = _codes(check_scenario(scenario=scenario, result=missing))
    assert "SCENARIO: suppressed_without_reason" in codes
    assert "SCENARIO: empty_composer" not in codes


@pytest.mark.asyncio
async def test_a7_llm_real_and_deterministic_share_empty_composer_semantics() -> None:
    scenario = _load("p10_02_assume_resume")
    run = await run_scenario_detailed(scenario)
    assert run.ok, "\n".join(run.errors)
    det = _codes(check_scenario(scenario=scenario, result=run, llm_real=False))
    live = _codes(check_scenario(scenario=scenario, result=run, llm_real=True))
    assert det == live
    assert "SCENARIO: empty_composer" not in det

    empty_customer = _fake_run(
        name=scenario["name"],
        turns=[_customer_turn(outbound=[])],
    )
    fail_det = _codes(check_scenario(scenario={"name": scenario["name"], "turns": [{}]}, result=empty_customer, llm_real=False))
    fail_live = _codes(check_scenario(scenario={"name": scenario["name"], "turns": [{}]}, result=empty_customer, llm_real=True))
    assert fail_det == fail_live
    assert "SCENARIO: empty_composer" in fail_det


@pytest.mark.asyncio
async def test_a8_admin_event_does_not_increase_runtime_call_count() -> None:
    scenario = _load("p10_02_assume_resume")
    run = await run_scenario_detailed(scenario)
    assert run.ok, "\n".join(run.errors)
    admin = [t for t in run.turns if t.get("event_kind") == "admin_event"]
    assert len(admin) == 2
    assert all(int(t.get("runtime_call_count") or t.get("runtime_calls") or 0) == 0 for t in admin)
    assert all(int(t.get("llm_calls") or 0) == 0 for t in admin)
    turn_sum = sum(int(t.get("runtime_call_count") or t.get("runtime_calls") or 0) for t in run.turns)
    assert run.runtime_calls == turn_sum
    assert run.runtime_calls == len(run.turns) - len(admin)
    customer = [t for t in run.turns if t.get("event_kind") != "admin_event"]
    assert all(int(t.get("runtime_call_count") or 0) == 1 for t in customer)
