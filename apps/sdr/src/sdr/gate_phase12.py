"""Phase 12 live-LLM gate then consolidated regression.

Usage (from apps/sdr, with OPENAI_API_KEY in local gitignored .env):

    uv run python -m sdr.gate_phase12
    uv run python -m sdr.gate_phase12 --gate-only
    uv run python -m sdr.gate_phase12 --regression-only

High-risk set repeats three times on the frozen candidate. Full regression
runs once, only if the gate is technically green. Summary LLM off. Isolated
seed. Clock frozen. Evolution/Supabase remote off. scheduler_hosted=false.

Does not version secrets or PII. Writes ``apps/sdr/.gate/phase12/<run_id>/``.
Automation never marks COMMERCIAL_PASS.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sdr.domain.clock import GOLDEN_CLOCK_ISO, set_clock
from sdr.gate_phase9 import _prepare_scenario
from sdr.replay.artifacts import git_head, restore_openai_key, write_meta
from sdr.replay.execution_meta import phase12_regression_meta
from sdr.replay.followup_harness import sanitize_artifact
from sdr.replay.round_report import build_round_report
from sdr.replay.runner import format_conversation, run_scenario_detailed, write_transcripts
from tests.golden.fixtures.seed_inventory_adapter import SEED_VERSION, load_seed, seed_sha256
from tests.golden.phase12.corpus import high_risk_cases, regression_paths

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".gate" / "phase12"
TZ_BRT = ZoneInfo("America/Sao_Paulo")
HIGH_RISK_REPEATS = 3

COMMERCIAL_RUBRIC = [
    "Respondeu à pergunta",
    "Reconheceu fatos novos",
    "Próxima ação adequada",
    "Uma ação principal",
    "Naturalidade",
    "Rapport",
    "Tom de questionário",
    "Pressão comercial",
    "Veículo específico",
    "Repetição",
    "Promessa indevida",
    "Informação inventada",
    "Quantidade de bubbles",
    "Utilidade para vendedor",
    "Aprovação comercial",
]


def _disable_summary_llm() -> None:
    os.environ["SDR_SUMMARY_LLM"] = "false"
    from sdr.config import get_settings

    get_settings.cache_clear()


def _ensure_openai_key() -> bool:
    if restore_openai_key():
        return True
    # Gitignored .env is not copied into worktrees. Load the primary local file
    # without printing or logging the token.
    sibling = ROOT.parents[1].parent / "facilcar" / "apps" / "sdr" / ".env"
    if not sibling.is_file():
        return False
    for raw in sibling.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "OPENAI_API_KEY":
            continue
        token = value.strip().strip("'").strip('"')
        if token:
            os.environ["OPENAI_API_KEY"] = token
            from sdr.config import get_settings

            get_settings.cache_clear()
            return bool((get_settings().openai_api_key or "").strip())
    return False


def _dump(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(sanitize_artifact(payload), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _rubric_markdown(name: str) -> str:
    lines = [
        f"# Revisão humana — `{name}`",
        "",
        "Aprovação comercial: `PENDING_HUMAN_REVIEW`",
        "",
        "A automação não marca `COMMERCIAL_PASS`.",
        "",
        "| Critério | Resultado |",
        "| --- | --- |",
    ]
    for criterion in COMMERCIAL_RUBRIC:
        default = "PENDING_HUMAN_REVIEW" if criterion == "Aprovação comercial" else ""
        lines.append(f"| {criterion} | {default} |")
    lines.append("")
    return "\n".join(lines)


def classify_run(run: Any) -> str:
    meta = dict(getattr(run, "execution_meta", None) or {})
    blob = json.dumps(meta, default=str)
    if "TEST_DOUBLE" in blob and meta.get("policy_mode") == "production_policy":
        return "HARNESS_FAIL"
    if meta.get("policy_mode") != "production_policy":
        return "HARNESS_FAIL"
    if meta.get("scheduler_mode") != "controlled_tick":
        return "HARNESS_FAIL"
    if meta.get("persistence_mode") != "isolated":
        return "HARNESS_FAIL"
    if meta.get("scheduler_hosted") is True:
        return "HARNESS_FAIL"
    if getattr(run, "llm_real", False) and meta.get("llm_mode") != "live":
        return "HARNESS_FAIL"
    if not getattr(run, "ok", False):
        return "TECHNICAL_FAIL"
    return "TECHNICAL_PASS"


async def _run_labeled(path: Path, label: str) -> Any:
    scenario = _prepare_scenario(json.loads(path.read_text(encoding="utf-8")))
    scenario["execution_mode"] = "production_policy"
    run = await run_scenario_detailed(
        scenario,
        show_trace=True,
        pool=object(),
        llm_real=True,
        use_live_inventory=False,
    )
    run.name = label
    print("\n" + format_conversation(run))
    return run


async def run_high_risk_gate() -> list[Any]:
    ordered: list[Any] = []
    for gate_id, path in high_risk_cases():
        name = path.stem
        for rep in range(HIGH_RISK_REPEATS):
            label = f"{gate_id}__{name}__rep{rep + 1}"
            ordered.append(await _run_labeled(path, label))
    return ordered


async def run_full_regression() -> list[Any]:
    ordered: list[Any] = []
    for path in regression_paths():
        ordered.append(await _run_labeled(path, path.stem))
    return ordered


def _write_artifacts(dest: Path, cases: list[Any], meta: dict[str, Any], *, kind: str) -> None:
    write_transcripts(cases, output_dir=dest)
    events: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []
    replies: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    visual: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    clock_jumps: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    cancels: list[dict[str, Any]] = []
    revisions: list[dict[str, Any]] = []
    ownership: list[dict[str, Any]] = []
    outbounds: list[dict[str, Any]] = []
    suppressions: list[dict[str, Any]] = []
    handoffs: list[dict[str, Any]] = []
    notifications: list[dict[str, Any]] = []
    crm_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    classifications: list[dict[str, Any]] = []

    for run in cases:
        status = classify_run(run)
        classifications.append(
            {
                "scenario": run.name,
                "technical": status,
                "commercial": "PENDING_HUMAN_REVIEW",
                "ok": bool(run.ok),
                "errors": list(run.errors or []),
                "retries": int(run.retry_count or 0),
                "fallbacks": int(run.fallback_count or 0),
                "execution_meta": dict(run.execution_meta or {}),
            }
        )
        events.append({"scenario": run.name, "events": list(run.events_executed or [])})
        batches.append({"scenario": run.name, "batches": list(run.inbound_batches or [])})
        clock_jumps.append({"scenario": run.name, "jumps": list(run.clock_jumps or [])})
        tasks.extend({"scenario": run.name, **row} for row in (run.followup_tasks or []))
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
                "context": (run.followup_evidence or {}).get("context_revision"),
            }
        )
        crm_rows.append(
            {
                "scenario": run.name,
                "lead_id": run.crm_lead_id,
                "handoff_count": int(run.crm_handoff_count or 0),
                "payload": (run.crm_report or {}).get("payload_sent"),
                "readback": (run.crm_report or {}).get("record_reread"),
                "matches_payload": (run.crm_report or {}).get("matches_payload"),
            }
        )
        summaries.append({"scenario": run.name, "summary": run.vendor_summary})
        handoffs.append(
            {
                "scenario": run.name,
                "handoff_count": int(run.crm_handoff_count or 0),
                "terminal": run.obtained_terminal,
            }
        )
        notifications.append(
            {
                "scenario": run.name,
                "handoff_count": int(run.crm_handoff_count or 0),
            }
        )
        for turn in run.turns or []:
            outbounds.append(
                {
                    "scenario": run.name,
                    "idx": turn.get("idx"),
                    "action": turn.get("action"),
                    "inbound": turn.get("inbound"),
                    "outbound": turn.get("outbound") or [],
                    "quoted": turn.get("quoted"),
                    "wait_state": turn.get("wait_state"),
                }
            )
            if turn.get("quoted"):
                replies.append({"scenario": run.name, "turn": turn.get("idx"), "quoted": turn.get("quoted")})
            if turn.get("vehicle_cards") or turn.get("outbound_media"):
                cards.append(
                    {
                        "scenario": run.name,
                        "turn": turn.get("idx"),
                        "cards": turn.get("vehicle_cards") or [],
                        "media": turn.get("outbound_media") or [],
                    }
                )
            if turn.get("document_extracted") or turn.get("content_type") == "DOCUMENT":
                documents.append(
                    {
                        "scenario": run.name,
                        "turn": turn.get("idx"),
                        "document": turn.get("document_extracted"),
                    }
                )
            if turn.get("suppressed_reason"):
                suppressions.append(
                    {
                        "scenario": run.name,
                        "turn": turn.get("idx"),
                        "reason": turn.get("suppressed_reason"),
                    }
                )
            actions.append(
                {
                    "scenario": run.name,
                    "turn": turn.get("idx"),
                    "action": turn.get("action"),
                    "ask_field": turn.get("ask_field"),
                }
            )
        for trace in run.traces or []:
            visual.append(
                {
                    "scenario": run.name,
                    "turn_id": trace.get("turn_id"),
                    "listing_metadata": trace.get("listing_metadata"),
                    "inventory_match": trace.get("inventory_match"),
                }
            )
            plans.append({"scenario": run.name, "turn_id": trace.get("turn_id"), "plan": trace.get("action_plan")})
            responses.append(
                {
                    "scenario": run.name,
                    "turn_id": trace.get("turn_id"),
                    "outbound": trace.get("composer_result") or [],
                    "fallback": trace.get("fallback"),
                    "retry": trace.get("retry"),
                }
            )

    _dump(dest / "events.json", events)
    _dump(dest / "batches.json", batches)
    _dump(dest / "replies.json", replies)
    _dump(dest / "cards_media.json", cards)
    _dump(dest / "documents.json", documents)
    _dump(dest / "visual_resolution.json", visual)
    _dump(dest / "plans.json", plans)
    _dump(dest / "responses.json", responses)
    _dump(dest / "actions.json", actions)
    _dump(dest / "clock_jumps.json", clock_jumps)
    _dump(dest / "followup_tasks.json", tasks)
    _dump(dest / "claims.json", claims)
    _dump(dest / "cancels.json", cancels)
    _dump(dest / "revisions.json", revisions)
    _dump(dest / "ownership.json", ownership)
    _dump(dest / "outbounds.json", outbounds)
    _dump(dest / "suppressions.json", suppressions)
    _dump(dest / "handoffs.json", handoffs)
    _dump(dest / "notifications.json", notifications)
    _dump(dest / "crm_payload_readback.json", crm_rows)
    _dump(dest / "summaries.json", summaries)
    _dump(dest / "classifications.json", classifications)
    _dump(
        dest / "execution_meta.json",
        [{"scenario": run.name, **dict(run.execution_meta or {})} for run in cases],
    )
    _dump(dest / "round_report.json", build_round_report(cases))
    _dump(
        dest / "config.json",
        {
            "kind": kind,
            "clock": GOLDEN_CLOCK_ISO,
            "timezone": "America/Sao_Paulo",
            "summary_llm": False,
            "inventory": "seed_isolated",
            "secrets": False,
            "remote_db": False,
            "evolution": False,
            "supabase": False,
            **phase12_regression_meta(llm_real=True).as_dict(),
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
            "scheduler_hosted": False,
        },
    )
    for run in cases:
        (dest / f"rubric_{run.name}.md").write_text(_rubric_markdown(run.name), encoding="utf-8")
        (dest / f"history_{run.name}.md").write_text(format_conversation(run) + "\n", encoding="utf-8")

    matrix_lines = [
        f"# Fase 12 — {kind} (PENDING_HUMAN_REVIEW)",
        "",
        "| Cenário | técnico | comercial | " + " | ".join(COMMERCIAL_RUBRIC[:-1]) + " |",
        "| --- | --- | --- | " + " | ".join("---" for _ in COMMERCIAL_RUBRIC[:-1]) + " |",
    ]
    for row in classifications:
        matrix_lines.append(
            f"| `{row['scenario']}` | {row['technical']} | PENDING_HUMAN_REVIEW | "
            + " | ".join("" for _ in COMMERCIAL_RUBRIC[:-1])
            + " |"
        )
    (dest / "commercial_matrix.md").write_text("\n".join(matrix_lines) + "\n", encoding="utf-8")

    failed = [row["scenario"] for row in classifications if row["technical"] != "TECHNICAL_PASS"]
    summary = [
        f"# Phase 12 {kind} `{dest.name}`",
        "",
        f"- commit: `{meta.get('commit')}`",
        f"- clock: `{GOLDEN_CLOCK_ISO}`",
        f"- runs: {len(cases)}",
        f"- technical: {'FAIL' if failed else 'PASS'}",
        "- commercial: PENDING_HUMAN_REVIEW",
        f"- policy_mode: production_policy",
        f"- scheduler_mode: controlled_tick",
        f"- persistence_mode: isolated",
        f"- scheduler_hosted: false",
        "",
    ]
    if failed:
        summary.append("FAILED:")
        summary.extend(f"- `{name}`" for name in failed)
        summary.append("")
    (dest / "latest.md").write_text("\n".join(summary), encoding="utf-8")
    (dest / "aggregate_report.md").write_text("\n".join(summary), encoding="utf-8")
    (OUT_DIR / "latest.md").write_text(
        f"# Phase 12\n\n{kind}: `{dest.name}`\npath: `{dest}`\n",
        encoding="utf-8",
    )
    return failed


def _meta(rid: str, cases: list[Any], *, kind: str) -> dict[str, Any]:
    return {
        "run_id": rid,
        "kind": kind,
        "commit": git_head(),
        "started_at": datetime.now(TZ_BRT).isoformat(),
        "timezone": "America/Sao_Paulo",
        "clock": GOLDEN_CLOCK_ISO,
        "models": {
            "understanding": "gpt-4.1-mini",
            "composer": "gpt-4.1-mini",
            "summary_llm": False,
        },
        "inventory": {
            "source": "seed_isolated",
            "seed_version": SEED_VERSION,
            "seed_sha256": seed_sha256(),
            "remote_consulted": False,
        },
        "run_count": len(cases),
        "commercial_quality": "PENDING_HUMAN_REVIEW",
        **phase12_regression_meta(llm_real=True).as_dict(),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sdr.gate_phase12")
    parser.add_argument("--gate-only", action="store_true")
    parser.add_argument("--regression-only", action="store_true")
    args = parser.parse_args(argv)
    os.environ.setdefault("SDR_TRACE", "true")
    if not _ensure_openai_key():
        print("GATE_ENVIRONMENT: OPENAI_API_KEY ausente — gate LLM bloqueado.")
        raise SystemExit(2)
    _disable_summary_llm()
    load_seed()
    set_clock(GOLDEN_CLOCK_ISO)

    if not args.regression_only:
        gate_cases = asyncio.run(run_high_risk_gate())
        gate_id = datetime.now(TZ_BRT).strftime("phase12-gate-%Y%m%dT%H%M%S")
        gate_dest = OUT_DIR / gate_id
        gate_dest.mkdir(parents=True, exist_ok=True)
        gate_meta = _meta(gate_id, gate_cases, kind="gate")
        write_meta(gate_dest, gate_meta)
        failed = _write_artifacts(gate_dest, gate_cases, gate_meta, kind="gate")
        print(f"\nGate directory: {gate_dest}")
        print("Aprovação comercial: PENDING_HUMAN_REVIEW")
        if failed:
            print("TECHNICAL_FAIL / HARNESS_FAIL:", ", ".join(failed))
            print("Regressão completa não iniciada.")
            raise SystemExit(1)
        if args.gate_only:
            return

    regression_cases = asyncio.run(run_full_regression())
    reg_id = datetime.now(TZ_BRT).strftime("phase12-regression-%Y%m%dT%H%M%S")
    reg_dest = OUT_DIR / reg_id
    reg_dest.mkdir(parents=True, exist_ok=True)
    reg_meta = _meta(reg_id, regression_cases, kind="regression")
    write_meta(reg_dest, reg_meta)
    failed = _write_artifacts(reg_dest, regression_cases, reg_meta, kind="regression")
    print(f"\nRegression directory: {reg_dest}")
    print("Aprovação comercial: PENDING_HUMAN_REVIEW")
    if failed:
        print("TECHNICAL_FAIL / HARNESS_FAIL:", ", ".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
