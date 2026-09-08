"""Phase 9 targeted live-LLM gate — qualification and conversational close.

Usage (from apps/sdr, with OPENAI_API_KEY in .env):

    uv run python -m sdr.gate_phase9

Real Understanding + Composer. Summary LLM off. Isolated seed inventory.
Clock frozen at 2026-09-07T10:00:00-03:00 (America/Sao_Paulo).
Does not run the 17-scenario regression. Does not version secrets or PII.
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
from sdr.replay.artifacts import git_head, restore_openai_key, write_meta
from sdr.replay.runner import format_conversation, run_scenario_detailed, write_transcripts
from tests.golden.fixtures.seed_inventory_adapter import SEED_VERSION, load_seed, seed_sha256

ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = ROOT / "tests" / "golden" / "phase9"
OUT_DIR = ROOT / ".gate" / "phase9"
TZ_BRT = ZoneInfo("America/Sao_Paulo")

REPEAT_THREE = (
    "p9_01_cumprimento_puro",
    "p9_04_financiamento_burst",
    "p9_05_reply_strada_2018",
    "p9_06_parcela_informada",
    "p9_07_somente_cnh",
    "p9_08_cnh_levo_resto_na_loja",
)

COMMERCIAL_MATRIX = [
    "Resposta à pergunta",
    "Reconhecimento do fato",
    "Ação principal",
    "Repetição",
    "Veículo correto",
    "Naturalidade",
    "Pressão",
    "Promessa indevida",
    "Informação inventada",
    "Quantidade de bubbles",
]


def list_phase9_scenarios() -> list[Path]:
    return sorted(SCENARIO_DIR.glob("p9_*.json"))


def _prepare_scenario(raw: dict[str, Any]) -> dict[str, Any]:
    scenario = json.loads(json.dumps(raw))
    init = scenario.setdefault("initial_state", {})
    facts = init.get("facts") if isinstance(init.get("facts"), dict) else {}
    shown = init.get("last_shown_vehicle_ids")
    if facts and shown and not init.get("last_inventory_search_key"):
        from sdr.domain.inventory_search import (
            build_inventory_search_request,
            inventory_search_key_from_request,
        )

        req = build_inventory_search_request(facts)
        init["last_inventory_search_key"] = inventory_search_key_from_request(
            req,
            last_shown_vehicle_ids=list(shown),
        )
    scenario["clock"] = scenario.get("clock") or GOLDEN_CLOCK_ISO
    return scenario


def _rubric_markdown(name: str) -> str:
    lines = [
        f"# Revisão humana — `{name}`",
        "",
        "Aprovação comercial: `PENDING_HUMAN_REVIEW`",
        "",
        "| Critério | Resultado |",
        "| --- | --- |",
    ]
    for criterion in COMMERCIAL_MATRIX:
        lines.append(f"| {criterion} |  |")
    lines.append("| Aprovação comercial | PENDING_HUMAN_REVIEW |")
    lines.append("")
    return "\n".join(lines)


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
    for path in list_phase9_scenarios():
        scenario = _prepare_scenario(json.loads(path.read_text(encoding="utf-8")))
        name = str(scenario.get("name") or path.stem)
        repeats = 3 if name in REPEAT_THREE else 1
        for rep in range(repeats):
            label = name if repeats == 1 else f"{name}__rep{rep + 1}"
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


def main() -> None:
    os.environ.setdefault("SDR_TRACE", "true")
    cases = asyncio.run(run_gate())
    rid = datetime.now(TZ_BRT).strftime("phase9-%Y%m%dT%H%M%S")
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
        "scenario_count": len(list_phase9_scenarios()),
        "run_count": len(cases),
        "commercial_quality": "PENDING_HUMAN_REVIEW",
    }
    write_meta(dest, meta)
    write_transcripts(cases, output_dir=dest)
    for run in cases:
        (dest / f"rubric_{run.name}.md").write_text(_rubric_markdown(run.name), encoding="utf-8")
    matrix_lines = [
        "# Fase 9 — matriz comercial (PENDING_HUMAN_REVIEW)",
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
    print(f"\nRun directory: {dest}")
    print("Aprovação comercial: PENDING_HUMAN_REVIEW")
    failed = [r.name for r in cases if not r.ok]
    if failed:
        print("TECHNICAL_FAIL:", ", ".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
