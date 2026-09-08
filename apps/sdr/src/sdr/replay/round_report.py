"""Stable counters for golden/LLM-real round reports.

Values are derived from ScenarioRunResult artifacts — never hardcoded scenario counts.
"""

from __future__ import annotations

from typing import Any, Iterable


def build_round_report(results: Iterable[Any]) -> dict[str, Any]:
    rows = list(results)
    technical_pass = [r for r in rows if getattr(r, "technical_status", "") == "TECHNICAL_PASS"]
    technical_fail = [r for r in rows if getattr(r, "technical_status", "") == "TECHNICAL_FAIL"]
    llm_attempted = [r for r in rows if getattr(r, "summary_llm_attempted", False)]
    llm_accepted = [
        r
        for r in rows
        if getattr(r, "summary_origin", "") == "llm" or getattr(r, "summary_used_llm", False)
    ]
    llm_rejected = [r for r in rows if getattr(r, "summary_llm_rejected", False)]
    empty_claims = [r for r in rows if getattr(r, "summary_empty_claims_rejected", False)]
    fallbacks = [r for r in rows if getattr(r, "summary_used_fallback", False)]
    fallbacks_validated = [
        r
        for r in fallbacks
        if (getattr(r, "summary_validation", None) or {}).get("pass") is True
    ]
    persist_ok = [
        r for r in rows if (getattr(r, "crm_report", None) or {}).get("matches_payload")
    ]
    pending = {
        r.name: "PENDING_HUMAN_REVIEW" for r in rows if getattr(r, "name", None)
    }
    return {
        "scenario_count": len(rows),
        "technical_pass_count": len(technical_pass),
        "technical_fail_count": len(technical_fail),
        "technical_status_by_scenario": {
            r.name: r.technical_status for r in rows
        },
        "pending_human_review_count": len(pending),
        "human_review": pending,
        "terminals": {r.name: r.obtained_terminal for r in rows},
        "failures": {r.name: r.errors for r in rows if not getattr(r, "ok", True)},
        "invariants_executed_by_scenario": {
            r.name: list(getattr(r, "invariants_executed", None) or [])
            for r in rows
        },
        "summary_origin_by_scenario": {
            r.name: getattr(r, "summary_origin", "") or ""
            for r in rows
        },
        "llm_summaries_attempted": len(llm_attempted),
        "llm_summaries_accepted": len(llm_accepted),
        "llm_summaries_rejected": len(llm_rejected),
        "llm_empty_claims_rejected": len(empty_claims),
        "deterministic_fallbacks_used": len(fallbacks),
        "deterministic_fallbacks_validated": len(fallbacks_validated),
        "composer_retries": sum(int(getattr(r, "composer_retries", 0) or 0) for r in rows),
        "questions_rejected": sum(int(getattr(r, "questions_rejected", 0) or 0) for r in rows),
        "dialogue_misaligned": sum(int(getattr(r, "dialogue_misaligned", 0) or 0) for r in rows),
        "persist_verified": len(persist_ok),
        "fallbacks": sum(int(getattr(r, "fallback_count", 0) or 0) for r in rows),
        "clock": getattr(rows[0], "clock_iso", None) if rows else None,
        "seed_version": getattr(rows[0], "seed_version", None) if rows else None,
        "seed_sha256": getattr(rows[0], "seed_sha256", None) if rows else None,
        "inventory_source": getattr(rows[0], "inventory_source", None) if rows else None,
        "understanding_model": getattr(rows[0], "understanding_model", None) if rows else None,
        "composer_model": getattr(rows[0], "composer_model", None) if rows else None,
        "runtime_calls": sum(int(getattr(r, "runtime_calls", 0) or 0) for r in rows),
        "location_sends": sum(int(getattr(r, "location_sends", 0) or 0) for r in rows),
        "inbound_batches": sum(len(getattr(r, "inbound_batches", None) or []) for r in rows),
        "visual_turns": sum(int(getattr(r, "visual_turns", 0) or 0) for r in rows),
        "identification_source_by_scenario": {
            r.name: getattr(r, "identification_source", None) for r in rows
        },
        "commercial_observations": {
            r.name: list(getattr(r, "commercial_observations", None) or [])
            for r in rows
        },
        "human_review_status": "PENDING_HUMAN_REVIEW",
    }


def recount_from_traces(results: Iterable[Any]) -> dict[str, int]:
    """Recompute a subset of counters from persist traces (consistency check)."""
    rows = list(results)
    dialogue = 0
    persist = 0
    for r in rows:
        for tr in getattr(r, "traces", None) or []:
            alignment = tr.get("dialogue_alignment")
            if isinstance(alignment, dict) and alignment.get("dialogue_alignment") is False:
                dialogue += 1
            elif tr.get("dialogue_alignment") is False:
                dialogue += 1
        report = getattr(r, "crm_report", None) or {}
        if report.get("matches_payload"):
            persist += 1
    return {
        "dialogue_misaligned": dialogue,
        "persist_verified": persist,
        "scenario_count": len(rows),
    }
