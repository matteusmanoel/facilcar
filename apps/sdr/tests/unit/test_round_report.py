"""Round-report counters must be derived from the artifacts they describe."""

from __future__ import annotations

from sdr.replay.round_report import build_round_report, recount_from_traces
from sdr.replay.runner import ScenarioRunResult, format_conversation


def _result(**kwargs) -> ScenarioRunResult:
    defaults = dict(
        ok=True,
        errors=[],
        name="scenario",
        technical_status="TECHNICAL_PASS",
        obtained_terminal="HANDOFF_VENDOR",
    )
    defaults.update(kwargs)
    return ScenarioRunResult(**defaults)


def test_round_report_counters_are_derived_from_results() -> None:
    results = [
        _result(
            name="a",
            summary_llm_attempted=True,
            summary_llm_rejected=True,
            summary_used_fallback=True,
            summary_empty_claims_rejected=True,
            summary_origin="deterministic_after_llm_reject",
            summary_validation={"pass": True},
            crm_report={"matches_payload": True},
            composer_retries=2,
            questions_rejected=1,
            dialogue_misaligned=0,
            traces=[{"dialogue_alignment": {"dialogue_alignment": True}}],
        ),
        _result(
            name="b",
            summary_llm_attempted=True,
            summary_used_llm=True,
            summary_origin="llm",
            summary_validation={"pass": True},
            crm_report={"matches_payload": True},
            traces=[{"dialogue_alignment": {"dialogue_alignment": True}}],
        ),
        _result(
            name="c",
            ok=False,
            errors=["fail"],
            technical_status="TECHNICAL_FAIL",
            summary_origin="deterministic",
            dialogue_misaligned=1,
            crm_report={"matches_payload": False},
            traces=[{"dialogue_alignment": {"dialogue_alignment": False}}],
        ),
        _result(
            name="d",
            summary_origin="deterministic_special_vendor_request",
            summary_validation={
                "pass": True,
                "claims": [],
                "claim_policy": "commercial_claims_not_applicable",
            },
            crm_report={"matches_payload": True},
            traces=[{"dialogue_alignment": True}],
        ),
    ]
    report = build_round_report(results)
    assert report["scenario_count"] == len(results)
    assert report["llm_summaries_attempted"] == sum(1 for r in results if r.summary_llm_attempted)
    assert report["llm_summaries_accepted"] == sum(
        1 for r in results if r.summary_origin == "llm" or r.summary_used_llm
    )
    assert report["llm_summaries_rejected"] == sum(1 for r in results if r.summary_llm_rejected)
    assert report["llm_empty_claims_rejected"] == sum(
        1 for r in results if r.summary_empty_claims_rejected
    )
    assert report["deterministic_fallbacks_used"] == sum(1 for r in results if r.summary_used_fallback)
    assert report["deterministic_fallbacks_validated"] == sum(
        1
        for r in results
        if r.summary_used_fallback and (r.summary_validation or {}).get("pass") is True
    )
    assert report["composer_retries"] == sum(r.composer_retries for r in results)
    assert report["questions_rejected"] == sum(r.questions_rejected for r in results)
    assert report["dialogue_misaligned"] == sum(r.dialogue_misaligned for r in results)
    assert report["persist_verified"] == sum(
        1 for r in results if (r.crm_report or {}).get("matches_payload")
    )
    assert report["technical_pass_count"] == sum(
        1 for r in results if r.technical_status == "TECHNICAL_PASS"
    )
    assert report["technical_fail_count"] == sum(
        1 for r in results if r.technical_status == "TECHNICAL_FAIL"
    )
    assert report["pending_human_review_count"] == len(results)
    assert all(v == "PENDING_HUMAN_REVIEW" for v in report["human_review"].values())
    assert report["llm_calls"] == sum(getattr(r, "llm_calls", 0) for r in results)
    assert report["suppressed_outbound"] == sum(
        getattr(r, "suppressed_outbound_count", 0) for r in results
    )
    recounted = recount_from_traces(results)
    assert recounted["scenario_count"] == report["scenario_count"]
    assert recounted["persist_verified"] == report["persist_verified"]
    assert recounted["dialogue_misaligned"] == report["dialogue_misaligned"]


def test_round_report_matches_persist_artifact_rows() -> None:
    persist_rows = [
        {"scenario": "a", "persist": {"matches_payload": True}},
        {"scenario": "b", "persist": {"matches_payload": True}},
        {"scenario": "c", "persist": {"matches_payload": False}},
    ]
    results = [
        _result(name=row["scenario"], crm_report=row["persist"])
        for row in persist_rows
    ]
    report = build_round_report(results)
    assert report["scenario_count"] == len(persist_rows)
    assert report["persist_verified"] == sum(
        1 for row in persist_rows if row["persist"]["matches_payload"]
    )


def test_transcript_separates_turn_intent_from_canonical_intent() -> None:
    result = _result(
        name="venda_direta",
        turns=[
            {
                "inbound": "Quero vender meu Corolla",
                "outbound": ["Me diga seu nome, por favor?"],
                "action": "ASK_INFO",
                "ask_field": "name",
                "turn_intent": "sale",
                "canonical_intent": "sale",
            },
            {
                "inbound": "Bruno Azevedo",
                "outbound": ["Anotei, Bruno."],
                "action": "ASK_INFO",
                "turn_intent": "unknown",
                "canonical_intent": "sale",
            },
        ],
    )
    text = format_conversation(result)
    assert "turn_intent=unknown" in text
    assert "canonical_intent=sale" in text
    assert "intent=unknown" not in text.replace("turn_intent=unknown", "")
