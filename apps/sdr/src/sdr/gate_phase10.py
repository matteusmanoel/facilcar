"""Phase 10 targeted live-LLM gate — handoff continuity, assume, and resume.

Usage (from apps/sdr, with OPENAI_API_KEY in .env):

    uv run python -m sdr.gate_phase10

Real Understanding + Composer. Summary LLM off. Isolated seed inventory.
Clock frozen at 2026-09-07T10:00:00-03:00 (America/Sao_Paulo).
Does not run the 17-scenario regression. Does not version secrets or PII.
Deterministic pytest lives in tests/golden/test_phase10_continuity.py.
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
OUT_DIR = ROOT / ".gate" / "phase10"
TZ_BRT = ZoneInfo("America/Sao_Paulo")

# gate_id, relative path from apps/sdr, repeats
GATE_CASES: tuple[tuple[str, Path, int], ...] = (
    ("G1", PHASE10_DIR / "p10_01_handoff_continuity.json", 3),
    ("E4E5", PHASE10_DIR / "p10_02_assume_resume.json", 1),
    ("E6", PHASE10_DIR / "p10_04_crm_same_lead.json", 1),
)


def _disable_summary_llm() -> None:
    os.environ["SDR_SUMMARY_LLM"] = "false"
    from sdr.config import get_settings

    get_settings.cache_clear()


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


def _write_latest(dest: Path) -> None:
    latest = OUT_DIR / "latest.md"
    latest.write_text(
        f"# Phase 10 gate\n\nrun: `{dest.name}`\npath: `{dest}`\n",
        encoding="utf-8",
    )


def main() -> None:
    os.environ.setdefault("SDR_TRACE", "true")
    cases = asyncio.run(run_gate())
    rid = datetime.now(TZ_BRT).strftime("phase10-%Y%m%dT%H%M%S")
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
    }
    write_meta(dest, meta)
    write_transcripts(cases, output_dir=dest)
    for run in cases:
        (dest / f"rubric_{run.name}.md").write_text(_rubric_markdown(run.name), encoding="utf-8")
    matrix_lines = [
        "# Fase 10 — matriz comercial (PENDING_HUMAN_REVIEW)",
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
        f"# Phase 10 gate `{rid}`",
        "",
        f"- commit: `{meta['commit']}`",
        f"- runs: {len(cases)}",
        f"- technical: {'FAIL' if failed else 'PASS'}",
        f"- commercial: PENDING_HUMAN_REVIEW",
        "",
    ]
    if failed:
        summary.append("TECHNICAL_FAIL:")
        summary.extend(f"- `{name}`" for name in failed)
        summary.append("")
    (dest / "latest.md").write_text("\n".join(summary), encoding="utf-8")
    _write_latest(dest)
    print(f"\nRun directory: {dest}")
    print("Aprovação comercial: PENDING_HUMAN_REVIEW")
    if failed:
        print("TECHNICAL_FAIL:", ", ".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
