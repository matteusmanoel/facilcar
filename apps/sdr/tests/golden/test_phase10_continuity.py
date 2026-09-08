"""Phase 10 replay — handoff continuity, assume, resume, CRM readback.

Deterministic pytest uses understand_return stubs. Live LLM belongs to
`python -m sdr.gate_phase10` after freeze.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdr.replay.round_report import build_round_report
from sdr.replay.runner import run_scenario_detailed

_PHASE10_DIR = Path(__file__).parent / "phase10"


def _scenario_ids() -> list[str]:
    return [p.stem for p in sorted(_PHASE10_DIR.glob("p10_*.json"))]


def _load(name: str) -> dict:
    return json.loads((_PHASE10_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_name", _scenario_ids())
async def test_phase10_golden_scenario(scenario_name: str) -> None:
    scenario = _load(scenario_name)
    run = await run_scenario_detailed(scenario, show_trace=False, pool=None)
    assert run.ok, "\n".join(run.errors)
    assert len(run.turns) == len(scenario["turns"])


@pytest.mark.asyncio
async def test_e1_e2_e3_handoff_is_not_end_of_conversation() -> None:
    run = await run_scenario_detailed(_load("p10_01_handoff_continuity"))
    assert run.ok, "\n".join(run.errors)
    actions = [str(t.get("action") or "").upper() for t in run.turns]
    assert actions[0] == "HANDOFF_VENDOR"
    assert actions[1] != "HANDOFF_VENDOR"
    assert run.turns[1].get("outbound")
    assert actions.count("HANDOFF_VENDOR") == 1
    assert int(run.crm_handoff_count) == 1
    assert run.obtained_terminal == "HANDOFF_VENDOR"


@pytest.mark.asyncio
async def test_e4_e5_assume_silence_then_resume_later_inbound() -> None:
    run = await run_scenario_detailed(_load("p10_02_assume_resume"))
    assert run.ok, "\n".join(run.errors)
    assert len(run.turns) == 6

    silenced = run.turns[3]
    assert silenced["inbound"] == "Quero financiar o Civic sem entrada"
    assert silenced.get("outbound") == []
    assert silenced.get("llm_calls") == 0
    assert silenced.get("inbound_persisted") is True
    assert str(silenced.get("bot_status") or "") == "HUMAN_ACTIVE"

    later = run.turns[5]
    assert later.get("outbound")
    assert "Quero financiar o Civic sem entrada" not in " ".join(later.get("outbound") or [])
    assert str(later.get("bot_status") or "") == "AI_RESUMED"

    assert run.llm_calls >= 1
    assert run.suppressed_outbound_count >= 1
    assert "ai_silenced" in (run.suppressed_outbound_reasons or [])
    assert int(run.crm_handoff_count) == 1


@pytest.mark.asyncio
async def test_e6_crm_readback_same_lead_after_post_handoff_update() -> None:
    run = await run_scenario_detailed(_load("p10_04_crm_same_lead"))
    assert run.ok, "\n".join(run.errors)
    assert run.crm_lead_id
    stored = (run.crm_report or {}).get("record_reread") or {}
    assert stored.get("id") == run.crm_lead_id
    fin = stored.get("financingRequest") or {}
    assert float(fin.get("desiredMonthlyPayment") or 0) == 1800.0
    assert stored.get("status") == "QUALIFIED"
    assert int(run.crm_handoff_count) == 1


@pytest.mark.asyncio
async def test_e7_e8_e9_counters_and_ownership_in_report() -> None:
    run = await run_scenario_detailed(_load("p10_02_assume_resume"))
    assert run.ok, "\n".join(run.errors)
    report = build_round_report([run])
    assert report["llm_calls"] == run.llm_calls
    assert report["suppressed_outbound"] == run.suppressed_outbound_count
    ownership = report["ownership_by_scenario"][run.name]
    assert ownership["botStatus"] == "AI_RESUMED"
    assert int(ownership["ownershipRevision"]) >= 2
    last_trace = run.traces[-1]
    assert last_trace.get("botStatus") == "AI_RESUMED"
    assert "ownershipRevision" in last_trace


@pytest.mark.asyncio
async def test_e10_principal_event_not_executed_fails_technical_pass() -> None:
    full = _load("p10_02_assume_resume")
    run = await run_scenario_detailed(full)
    assert run.technical_status == "TECHNICAL_PASS"
    assert "SCENARIO: principal_event_not_executed" not in " ".join(run.errors)

    from sdr.replay.runner import ScenarioRunResult
    from tests.golden.invariants import check_scenario

    fake = ScenarioRunResult(
        ok=True,
        errors=[],
        name=full["name"],
        turns=[{"idx": 0, "action": "HANDOFF_VENDOR", "inbound": "x", "outbound": ["ok"]}],
        technical_status="TECHNICAL_PASS",
        obtained_terminal="HANDOFF_VENDOR",
    )
    violations = check_scenario(scenario=full, result=fake)
    codes = [v.invariant for v in violations]
    assert "SCENARIO: principal_event_not_executed" in codes


def test_gate_phase10_output_dir_is_gitignored() -> None:
    from sdr.gate_phase10 import OUT_DIR, ROOT

    assert OUT_DIR == ROOT / ".gate" / "phase10"
    gitignore = ROOT.joinpath(".gitignore").read_text(encoding="utf-8")
    assert ".gate/" in gitignore
