"""Phase 10R targeted live-LLM gate — G1–G3, G4/G6 assume-resume, G7.

Usage (from apps/sdr, with OPENAI_API_KEY in .env):

    uv run python -m sdr.gate_phase10r

Real Understanding + Composer. Summary LLM off. Isolated seed inventory.
Clock frozen at 2026-09-07T10:00:00-03:00 (America/Sao_Paulo).
Does not run the 17-scenario regression. Does not version secrets or PII.
G4 assume-before-inbound and G5 races stay deterministic pytest
(`tests/golden/test_phase10r_matrix.py`). empty_composer on admin events
is Frente A harness ownership — this runner still records the case.

Deterministic pytest lives in tests/golden/test_phase10r_matrix.py.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sdr.domain.clock import GOLDEN_CLOCK_ISO, set_clock
from sdr.gate_phase9 import COMMERCIAL_MATRIX, _prepare_scenario, _rubric_markdown
from sdr.replay.artifacts import git_head, restore_openai_key, write_meta
from sdr.replay.runner import format_conversation, run_scenario_detailed, write_transcripts
from tests.golden.fixtures.seed_inventory_adapter import SEED_VERSION, load_seed, seed_sha256

ROOT = Path(__file__).resolve().parents[2]
PHASE10_DIR = ROOT / "tests" / "golden" / "phase10"
PHASE10R_DIR = ROOT / "tests" / "golden" / "phase10r"
OUT_DIR = ROOT / ".gate" / "phase10r"
TZ_BRT = ZoneInfo("America/Sao_Paulo")

# gate_id, path, repeats — one live run each; races G4/G5 stay pytest-only.
GATE_CASES: tuple[tuple[str, Path, int], ...] = (
    ("G4G6", PHASE10_DIR / "p10_02_assume_resume.json", 1),
    ("G1", PHASE10R_DIR / "g1_document_after_handoff.json", 1),
    ("G2", PHASE10R_DIR / "g2_equipment_question_after_handoff.json", 1),
    ("G3", PHASE10R_DIR / "g3_visit_time_change_after_handoff.json", 1),
    ("G7", PHASE10R_DIR / "g7_quoted_other_strada_after_handoff.json", 1),
)


def _disable_summary_llm() -> None:
    os.environ["SDR_SUMMARY_LLM"] = "false"
    from sdr.config import get_settings

    get_settings.cache_clear()


def _dump(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: _sanitize(v)
            for k, v in value.items()
            if str(k).lower() not in {"authorization", "api_key", "openai_api_key", "token", "secret"}
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


async def run_gate() -> list[Any]:
    if not restore_openai_key():
        raise SystemExit("OPENAI_API_KEY ausente — gate LLM bloqueado.")
    _disable_summary_llm()
    load_seed()
    set_clock(GOLDEN_CLOCK_ISO)

    ordered: list[Any] = []
    for gate_id, path, repeats in GATE_CASES:
        scenario = _prepare_scenario(json.loads(path.read_text(encoding="utf-8")))
        name = str(scenario.get("name") or path.stem)
        for rep in range(repeats):
            label = f"{gate_id}__{name}" if repeats == 1 else f"{gate_id}__{name}__rep{rep + 1}"
            run = await run_scenario_detailed(
                scenario,
                show_trace=True,
                pool=object(),
                llm_real=True,
                use_live_inventory=False,
            )
            run.name = label
            ordered.append(run)
            print("\n" + format_conversation(run))
    return ordered


def _write_phase10r_artifacts(dest: Path, cases: list[Any], meta: dict[str, Any]) -> None:
    write_transcripts(cases, output_dir=dest)
    history = dest / "latest.md"
    if history.is_file():
        (dest / "history.md").write_text(history.read_text(encoding="utf-8"), encoding="utf-8")

    mapping = json.loads((PHASE10R_DIR / "g1_g7_mapping.json").read_text(encoding="utf-8"))
    skips = json.loads((PHASE10R_DIR / "skips.json").read_text(encoding="utf-8"))
    _dump(dest / "g1_g7.json", mapping)
    _dump(dest / "skips.json", skips)

    admin_events: list[dict[str, Any]] = []
    ownership: list[dict[str, Any]] = []
    revisions: list[dict[str, Any]] = []
    composer: list[dict[str, Any]] = []
    outbounds: list[dict[str, Any]] = []
    suppressions: list[dict[str, Any]] = []
    notifications: list[dict[str, Any]] = []
    crm_rows: list[dict[str, Any]] = []
    events_executed: list[dict[str, Any]] = []

    for run in cases:
        ownership.append(
            {
                "scenario": run.name,
                "botStatus": run.bot_status,
                "ownershipRevision": int(run.ownership_revision or 0),
            }
        )
        revisions.append(
            {
                "scenario": run.name,
                "ownershipRevision": int(run.ownership_revision or 0),
                "crm_lead_id": run.crm_lead_id,
            }
        )
        suppressions.append(
            {
                "scenario": run.name,
                "count": int(run.suppressed_outbound_count or 0),
                "reasons": list(run.suppressed_outbound_reasons or []),
            }
        )
        notifications.append(
            {
                "scenario": run.name,
                "crm_handoff_count": int(run.crm_handoff_count or 0),
                "obtained_terminal": run.obtained_terminal,
            }
        )
        crm_rows.append(
            {
                "scenario": run.name,
                "lead_id": run.crm_lead_id,
                "handoff_count": int(run.crm_handoff_count or 0),
                "payload": _sanitize((run.crm_report or {}).get("payload_sent")),
                "readback": _sanitize((run.crm_report or {}).get("record_reread")),
                "matches_payload": (run.crm_report or {}).get("matches_payload"),
            }
        )
        events_executed.append({"scenario": run.name, "events": list(run.events_executed or [])})
        for turn in run.turns or []:
            if turn.get("admin_event"):
                admin_events.append(
                    {
                        "scenario": run.name,
                        "idx": turn.get("idx"),
                        "admin_event": turn.get("admin_event"),
                        "bot_status": turn.get("bot_status"),
                        "ownership_revision": turn.get("ownership_revision"),
                        "outbound": turn.get("outbound") or [],
                    }
                )
            outbounds.append(
                {
                    "scenario": run.name,
                    "idx": turn.get("idx"),
                    "inbound": turn.get("inbound"),
                    "action": turn.get("action"),
                    "outbound": turn.get("outbound") or [],
                }
            )
        for trace in run.traces or []:
            composer.append(
                {
                    "scenario": run.name,
                    "turn_id": trace.get("turn_id"),
                    "expected_action": (trace.get("action_plan") or {}).get("action"),
                    "actual_outbound": trace.get("composer_result") or [],
                    "composer_model": trace.get("composer_model"),
                    "fallback": trace.get("fallback"),
                    "admin_event": trace.get("admin_event"),
                }
            )

    _dump(dest / "admin_events.json", admin_events)
    _dump(dest / "ownership.json", ownership)
    _dump(dest / "revisions.json", revisions)
    _dump(dest / "composer_expected_actual.json", composer)
    _dump(dest / "outbounds.json", outbounds)
    _dump(dest / "suppressions.json", suppressions)
    _dump(dest / "notification_dispatch.json", notifications)
    _dump(dest / "crm_payload_readback.json", crm_rows)
    _dump(dest / "events_executed.json", events_executed)
    _dump(
        dest / "provenance.json",
        {
            "commit": meta.get("commit"),
            "clock": meta.get("clock"),
            "timezone": meta.get("timezone"),
            "models": meta.get("models"),
            "inventory": meta.get("inventory"),
            "summary_llm": False,
            "secrets": False,
            "remote_db": False,
        },
    )


def _write_latest(dest: Path) -> None:
    latest = OUT_DIR / "latest.md"
    latest.write_text(
        f"# Phase 10R gate\n\nrun: `{dest.name}`\npath: `{dest}`\n",
        encoding="utf-8",
    )


def main() -> None:
    os.environ.setdefault("SDR_TRACE", "true")
    cases = asyncio.run(run_gate())
    rid = datetime.now(TZ_BRT).strftime("phase10r-%Y%m%dT%H%M%S")
    dest = OUT_DIR / rid
    dest.mkdir(parents=True, exist_ok=True)
    meta = {
        "run_id": rid,
        "commit": git_head(),
        "started_at": datetime.now(TZ_BRT).isoformat(),
        "timezone": "America/Sao_Paulo",
        "clock": GOLDEN_CLOCK_ISO,
        "models": {
            "understanding": cases[0].understanding_model if cases else None,
            "composer": cases[0].composer_model if cases else None,
            "summary_llm": False,
        },
        "inventory": {
            "source": "seed_isolated",
            "seed_version": SEED_VERSION,
            "seed_sha256": seed_sha256(),
            "remote_consulted": False,
        },
        "gate_cases": [gate_id for gate_id, _path, _repeats in GATE_CASES],
        "run_count": len(cases),
        "commercial_quality": "PENDING_HUMAN_REVIEW",
        "g5_races": "pytest_only",
        "g4_assume_before_inbound": "pytest_plus_p10_02",
    }
    write_meta(dest, meta)
    _write_phase10r_artifacts(dest, cases, meta)
    for run in cases:
        (dest / f"rubric_{run.name}.md").write_text(_rubric_markdown(run.name), encoding="utf-8")
    matrix_lines = [
        "# Fase 10R — matriz comercial (PENDING_HUMAN_REVIEW)",
        "",
        "| Cenário | " + " | ".join(COMMERCIAL_MATRIX) + " | Aprovação |",
        "| --- | " + " | ".join("---" for _ in COMMERCIAL_MATRIX) + " | --- |",
    ]
    for run in cases:
        matrix_lines.append(
            f"| `{run.name}` | "
            + " | ".join("" for _ in COMMERCIAL_MATRIX)
            + " | PENDING_HUMAN_REVIEW |"
        )
    (dest / "commercial_matrix.md").write_text("\n".join(matrix_lines) + "\n", encoding="utf-8")
    failed = [r.name for r in cases if not r.ok]
    summary = [
        f"# Phase 10R gate `{rid}`",
        "",
        f"- commit: `{meta['commit']}`",
        f"- clock: `{GOLDEN_CLOCK_ISO}`",
        f"- runs: {len(cases)}",
        f"- technical: {'FAIL' if failed else 'PASS'}",
        f"- commercial: PENDING_HUMAN_REVIEW",
        f"- G5 races: pytest-only (`test_phase10r_matrix.py`)",
        "",
    ]
    if failed:
        summary.append("TECHNICAL_FAIL:")
        summary.extend(f"- `{name}`" for name in failed)
        summary.append("")
    (dest / "latest.md").write_text("\n".join(summary), encoding="utf-8")
    (dest / "aggregate_report.md").write_text("\n".join(summary), encoding="utf-8")
    _write_latest(dest)
    print(f"\nRun directory: {dest}")
    print("Aprovação comercial: PENDING_HUMAN_REVIEW")
    if failed:
        print("TECHNICAL_FAIL:", ", ".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
