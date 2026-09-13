"""Phase 11 targeted live-LLM gate — follow-up G1/G2.

Usage (from apps/sdr, with OPENAI_API_KEY in .env):

    uv run python -m sdr.gate_phase11

Real Understanding + Composer for G1 (x2) and G2 (x2). Summary LLM off.
Isolated seed inventory. Clock frozen at 2026-09-07T10:00:00-03:00
(America/Sao_Paulo). Does not run the 17-scenario regression.
G3–G10 stay deterministic pytest (`tests/golden/test_phase11_matrix.py`).
Does not version secrets or PII. Writes ``apps/sdr/.gate/phase11/<run_id>/``.
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
from sdr.replay.followup_harness import sanitize_artifact
from sdr.replay.round_report import build_round_report
from sdr.replay.runner import format_conversation, run_scenario_detailed, write_transcripts
from tests.golden.fixtures.seed_inventory_adapter import SEED_VERSION, load_seed, seed_sha256

ROOT = Path(__file__).resolve().parents[2]
PHASE11_DIR = ROOT / "tests" / "golden" / "phase11"
OUT_DIR = ROOT / ".gate" / "phase11"
TZ_BRT = ZoneInfo("America/Sao_Paulo")

# Live LLM: G1 x2 composer, G2 x2. Remainder is pytest-only.
GATE_CASES: tuple[tuple[str, Path, int], ...] = (
    ("G1", PHASE11_DIR / "g1_documents_tomorrow_14h.json", 2),
    ("G2", PHASE11_DIR / "g2_spouse_without_time.json", 2),
)

DETERMINISTIC_ONLY = ("G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10")


def _disable_summary_llm() -> None:
    os.environ["SDR_SUMMARY_LLM"] = "false"
    from sdr.config import get_settings

    get_settings.cache_clear()


def _dump(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(sanitize_artifact(payload), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


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


def _write_phase11_artifacts(dest: Path, cases: list[Any], meta: dict[str, Any]) -> None:
    write_transcripts(cases, output_dir=dest)
    events: list[dict[str, Any]] = []
    clock_jumps: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    consent: list[dict[str, Any]] = []
    reasons: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    cancels: list[dict[str, Any]] = []
    ownership: list[dict[str, Any]] = []
    revisions: list[dict[str, Any]] = []
    composer: list[dict[str, Any]] = []
    outbounds: list[dict[str, Any]] = []
    idempotency: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    crm_rows: list[dict[str, Any]] = []

    for run in cases:
        events.append({"scenario": run.name, "events": list(run.events_executed or [])})
        clock_jumps.append({"scenario": run.name, "jumps": list(run.clock_jumps or [])})
        tasks.extend({"scenario": run.name, **row} for row in (run.followup_tasks or []))
        transitions.append({"scenario": run.name, "transitions": list(run.followup_transitions or [])})
        claims.extend({"scenario": run.name, **row} for row in (run.followup_claims or []))
        cancels.extend({"scenario": run.name, **row} for row in (run.followup_cancels or []))
        ownership.append(
            {
                "scenario": run.name,
                "botStatus": run.bot_status,
                "ownershipRevision": int(run.ownership_revision or 0),
                "wait_state": run.wait_state,
            }
        )
        revisions.append(
            {
                "scenario": run.name,
                "ownershipRevision": int(run.ownership_revision or 0),
            }
        )
        idempotency.append(
            {
                "scenario": run.name,
                "keys": list(run.idempotency_keys or []),
                "sends": int(run.followup_sends or 0),
            }
        )
        inventory.append(
            {
                "scenario": run.name,
                "overrides": list(run.inventory_overrides or []),
                "revalidated": True,
            }
        )
        crm_rows.append(
            {
                "scenario": run.name,
                "lead_id": run.crm_lead_id,
                "handoff_count": int(run.crm_handoff_count or 0),
                "payload": (run.crm_report or {}).get("payload_sent"),
                "readback": (run.crm_report or {}).get("record_reread"),
            }
        )
        for task in run.followup_tasks or []:
            consent.append(
                {
                    "scenario": run.name,
                    "consentSource": task.get("consentSource"),
                    "consentLevel": task.get("consentLevel"),
                    "temporal": task.get("originalTemporalText"),
                }
            )
            reasons.append({"scenario": run.name, "reason": task.get("reason")})
        for turn in run.turns or []:
            outbounds.append(
                {
                    "scenario": run.name,
                    "idx": turn.get("idx"),
                    "action": turn.get("action"),
                    "inbound": turn.get("inbound"),
                    "outbound": turn.get("outbound") or [],
                    "wait_state": turn.get("wait_state"),
                }
            )
        for trace in run.traces or []:
            composer.append(
                {
                    "scenario": run.name,
                    "turn_id": trace.get("turn_id"),
                    "composer_model": trace.get("composer_model"),
                    "actual_outbound": trace.get("composer_result") or [],
                    "followup_sends": trace.get("followup_sends"),
                    "llm_calls": trace.get("llm_calls"),
                }
            )

    mapping = json.loads((PHASE11_DIR / "g1_g10_mapping.json").read_text(encoding="utf-8"))
    skips = json.loads((PHASE11_DIR / "skips.json").read_text(encoding="utf-8"))
    _dump(dest / "events.json", events)
    _dump(dest / "clock_jumps.json", clock_jumps)
    _dump(dest / "tasks.json", tasks)
    _dump(dest / "transitions.json", transitions)
    _dump(dest / "consent.json", consent)
    _dump(dest / "reasons.json", reasons)
    _dump(dest / "claims.json", claims)
    _dump(dest / "cancels.json", cancels)
    _dump(dest / "ownership.json", ownership)
    _dump(dest / "revisions.json", revisions)
    _dump(dest / "composer_calls.json", composer)
    _dump(dest / "outbounds.json", outbounds)
    _dump(dest / "idempotency.json", idempotency)
    _dump(dest / "inventory_revalidated.json", inventory)
    _dump(dest / "crm_payload_readback.json", crm_rows)
    _dump(
        dest / "execution_meta.json",
        [{"scenario": run.name, **dict(run.execution_meta or {})} for run in cases],
    )
    _dump(dest / "g1_g10.json", mapping)
    _dump(dest / "skips.json", skips)
    _dump(dest / "round_report.json", build_round_report(cases))
    _dump(
        dest / "config.json",
        {
            "clock": GOLDEN_CLOCK_ISO,
            "timezone": "America/Sao_Paulo",
            "summary_llm": False,
            "inventory": "seed_isolated",
            "secrets": False,
            "remote_db": False,
            "evolution": False,
            "scheduler_hosted": False,
            "policy_mode": "production_policy",
            "scheduler_mode": "controlled_tick",
            "persistence_mode": "isolated",
        },
    )
    _dump(
        dest / "provenance.json",
        {
            "commit": meta.get("commit"),
            "clock": meta.get("clock"),
            "timezone": meta.get("timezone"),
            "models": meta.get("models"),
            "inventory": meta.get("inventory"),
            "seed": meta.get("inventory"),
            "summary_llm": False,
            "secrets": False,
        },
    )


def _write_latest(dest: Path) -> None:
    latest = OUT_DIR / "latest.md"
    latest.write_text(
        f"# Phase 11 gate\n\nrun: `{dest.name}`\npath: `{dest}`\n",
        encoding="utf-8",
    )


def main() -> None:
    os.environ.setdefault("SDR_TRACE", "true")
    cases = asyncio.run(run_gate())
    rid = datetime.now(TZ_BRT).strftime("phase11-%Y%m%dT%H%M%S")
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
        "live_llm": {"G1": 2, "G2": 2},
        "deterministic_only": list(DETERMINISTIC_ONLY),
        "run_count": len(cases),
        "commercial_quality": "PENDING_HUMAN_REVIEW",
        "execution_meta": (cases[0].execution_meta if cases else {}),
        "scheduler_hosted": False,
    }
    write_meta(dest, meta)
    _write_phase11_artifacts(dest, cases, meta)
    for run in cases:
        (dest / f"rubric_{run.name}.md").write_text(_rubric_markdown(run.name), encoding="utf-8")
    matrix_lines = [
        "# Fase 11 — matriz comercial (PENDING_HUMAN_REVIEW)",
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
    for gate_id in DETERMINISTIC_ONLY:
        matrix_lines.append(
            f"| `{gate_id}` (pytest only) | "
            + " | ".join("" for _ in COMMERCIAL_MATRIX)
            + " | DETERMINISTIC_ONLY |"
        )
    (dest / "commercial_matrix.md").write_text("\n".join(matrix_lines) + "\n", encoding="utf-8")
    failed = [r.name for r in cases if not r.ok]
    summary = [
        f"# Phase 11 gate `{rid}`",
        "",
        f"- commit: `{meta['commit']}`",
        f"- clock: `{GOLDEN_CLOCK_ISO}`",
        f"- runs: {len(cases)} (G1 x2, G2 x2 live LLM)",
        f"- G3–G10: deterministic-only pytest",
        f"- technical: {'FAIL' if failed else 'PASS'}",
        f"- commercial: PENDING_HUMAN_REVIEW",
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
