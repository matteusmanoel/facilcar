"""Phase 12 corpus and execution-metadata contracts (deterministic)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdr.application.followup_runtime import EXECUTION_MODE_PRODUCTION
from sdr.gate_phase12 import classify_run
from sdr.replay.execution_meta import phase12_regression_meta
from sdr.replay.runner import run_scenario_detailed
from tests.golden.phase12.corpus import (
    COVERAGE,
    CORE_17,
    HIGH_RISK,
    core_paths,
    high_risk_cases,
    regression_paths,
)

_GOLDEN = Path(__file__).parent


def test_core_17_exist() -> None:
    assert len(CORE_17) == 17
    for path in core_paths():
        assert path.is_file(), path.name


def test_coverage_matrix_covers_contracts_01_to_31() -> None:
    ids = [row[0] for row in COVERAGE]
    assert ids == [f"{i:02d}" for i in range(1, 32)]
    matrix = (_GOLDEN / "phase12" / "coverage_matrix.md").read_text(encoding="utf-8")
    for contract_id, _label, files in COVERAGE:
        assert contract_id in matrix
        for name in files:
            assert name in matrix


def test_high_risk_and_regression_files_exist() -> None:
    assert len(HIGH_RISK) == 10
    for _gate_id, path in high_risk_cases():
        assert path.is_file(), path.name
    for path in regression_paths():
        assert path.is_file(), path.name


def test_phase12_execution_meta_has_no_contradictory_double() -> None:
    meta = phase12_regression_meta(llm_real=True).as_dict()
    assert meta["policy_mode"] == "production_policy"
    assert meta["scheduler_mode"] == "controlled_tick"
    assert meta["persistence_mode"] == "isolated"
    assert meta["scheduler_hosted"] is False
    assert meta["llm_mode"] == "live"
    blob = json.dumps(meta)
    assert "TEST_DOUBLE" not in blob
    assert "followup_harness_double" not in blob


@pytest.mark.asyncio
async def test_g1_unavailable_callback_is_one_primary_followup() -> None:
    path = _GOLDEN / "phase11" / "g1_documents_tomorrow_14h.json"
    scenario = json.loads(path.read_text(encoding="utf-8"))
    run = await run_scenario_detailed(scenario)
    assert run.ok, "\n".join(run.errors)
    assert classify_run(run) == "TECHNICAL_PASS"
    assert run.execution_meta["policy_mode"] == EXECUTION_MODE_PRODUCTION
    assert run.execution_meta["scheduler_mode"] == "controlled_tick"
    assert run.execution_meta["llm_mode"] == "stub"
    assert run.execution_meta["scheduler_hosted"] is False
    blob = " ".join(
        " ".join(t.get("outbound") or [])
        for t in run.turns
        if str(t.get("action") or "") in {"SCHEDULER_TICK", "FOLLOWUP_SEND"}
        or str(t.get("event_kind") or "") == "scheduler_tick"
    ).lower()
    assert "ia enviar" not in blob
    assert run.followup_sends == 1


def test_gate_phase12_output_dir_is_gitignored() -> None:
    from sdr.gate_phase12 import OUT_DIR, ROOT

    assert OUT_DIR == ROOT / ".gate" / "phase12"
    gitignore = ROOT.joinpath(".gitignore").read_text(encoding="utf-8")
    assert ".gate/" in gitignore
