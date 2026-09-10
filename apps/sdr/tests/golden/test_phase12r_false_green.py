"""Phase 12R golden reproductions — documents, CNH, resume summary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdr.replay.runner import run_scenario_detailed

_GOLDEN = Path(__file__).parent


def _load(*parts: str) -> dict:
    return json.loads((_GOLDEN.joinpath(*parts)).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_p9_09_unavailable_docs_are_not_a_visit() -> None:
    run = await run_scenario_detailed(_load("phase9", "p9_09_documentos_indisponiveis.json"))
    assert run.ok, "\n".join(run.errors)
    last = (run.turns or [{}])[-1]
    assert str(last.get("action") or "").upper() != "REGISTER_VISIT_INTEREST"
    joined = " ".join(last.get("outbound") or []).lower()
    assert "9h30" not in joined
    assert run.followup_sends == 0


@pytest.mark.asyncio
async def test_p9_07_cnh_only_is_documentary() -> None:
    run = await run_scenario_detailed(_load("phase9", "p9_07_somente_cnh.json"))
    assert run.ok, "\n".join(run.errors)
    last = (run.turns or [{}])[-1]
    assert str(last.get("action") or "").upper() != "REGISTER_VISIT_INTEREST"
    assert last.get("ask_field") == "documents"


@pytest.mark.asyncio
async def test_p10_02_summary_keeps_civic_after_resume() -> None:
    run = await run_scenario_detailed(_load("phase10", "p10_02_assume_resume.json"))
    assert run.ok, "\n".join(run.errors)
    summary = run.vendor_summary or ""
    assert "Civic" in summary
    assert "Carla" in summary
    assert int(run.crm_handoff_count or 0) <= 1


@pytest.mark.asyncio
async def test_fox_cnh_turn_does_not_invite_visit() -> None:
    run = await run_scenario_detailed(_load("scenarios", "whatsapp_fox_image_financing_burst_visit.json"))
    assert run.ok, "\n".join(run.errors)
    cnh = next(t for t in run.turns if "CNH" in str(t.get("inbound") or "").upper())
    assert str(cnh.get("action") or "").upper() != "REGISTER_VISIT_INTEREST"
    joined = " ".join(cnh.get("outbound") or []).lower()
    assert "9h30" not in joined
