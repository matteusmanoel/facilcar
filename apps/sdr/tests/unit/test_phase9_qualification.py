"""Phase 9 — qualification policy, primary vehicle label, one action per turn.

Tests A–T are semantic/state contracts. Exact copy is not required except
deliberate deterministic receipts such as ``Recebi sua CNH``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.dialogue_plan import (
    DialogueAct,
    build_dialogue_plan,
    contains_financing_approval_claim,
)
from sdr.domain.document_status import parse_document_deferral
from sdr.domain.financial_promises import contains_forbidden_financial_promise
from sdr.domain.introduction import introduction_smalltalk_bubbles, response_objective_for
from sdr.domain.merge import deterministic_merge
from sdr.domain.qualification_policy import (
    ACT_INVITE_VISIT,
    ENRICHMENT_ASK_LIMIT,
    PRIMARY_ASK_REMAINING_DOCUMENTS,
    financing_documents_applicable,
    remaining_document_components,
    should_ask_remaining_documents,
)
from sdr.domain.qualifications import field_is_applicable, next_ask_field, refresh_actionability
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
    TurnFacts,
)
from sdr.domain.vehicle_catalog import conversational_label_for_id, register_catalog_vehicles
from sdr.domain.vendor_summary import compose_vendor_summary
from sdr.understanding.validator import validate_dialogue_plan

from tests.golden.fixtures.seed_inventory_adapter import load_seed
from tests.golden.invariants import _FORBIDDEN_PROMISE_PATTERNS

SCENARIOS = Path(__file__).resolve().parents[1] / "golden" / "scenarios"

SAFE_TAXA_DISCLAIMER = (
    "É possível simular o financiamento sem entrada, mas a aprovação, "
    "taxa e prazo dependem da análise da financeira."
)


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t-phase9",
        customer=CustomerState(phone="5511999990009", name="Bruno Azevedo"),
        intent=kwargs.pop("intent", BusinessIntent.PURCHASE_FINANCING),
        language="pt-BR",
        facts=kwargs.pop("facts", {}),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return refresh_actionability(base)


def _financing_ready(**kwargs) -> ConversationCanonicalState:
    facts = {
        "desired_model": "Strada",
        "desired_vehicle_text": "Strada",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 1500,
        "name": "Bruno Azevedo",
        **kwargs.pop("facts", {}),
    }
    shown = kwargs.pop("last_shown_vehicle_ids", ["VH-STRADA-2021", "VH-STRADA-2017", "VH-STRADA-2018"])
    return _state(
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        last_shown_vehicle_ids=shown,
        documents_asked=True,
        installment_asked=True,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# A–C  taxa disclaimer vs promise
# ---------------------------------------------------------------------------

def test_a_safe_taxa_disclaimer_is_not_a_financial_promise() -> None:
    assert contains_forbidden_financial_promise(SAFE_TAXA_DISCLAIMER) is False
    for pattern in _FORBIDDEN_PROMISE_PATTERNS:
        assert pattern.search(SAFE_TAXA_DISCLAIMER) is None, pattern.pattern


def test_a_whatsapp_fixtures_do_not_forbid_isolated_taxa() -> None:
    for name in (
        "whatsapp_fox_image_financing_burst_visit.json",
        "whatsapp_strada_quoted_primary_financing_visit.json",
    ):
        data = json.loads((SCENARIOS / name).read_text(encoding="utf-8"))
        for idx, turn in enumerate(data["turns"]):
            forbidden = [str(item).lower() for item in (turn.get("forbidden_in_outbound") or [])]
            assert "taxa" not in forbidden, f"{name} turn {idx} still forbids isolated 'taxa'"


def test_b_invented_numeric_rate_is_still_a_promise() -> None:
    assert contains_forbidden_financial_promise("A taxa será de 1,5%.") is True
    assert contains_forbidden_financial_promise("Conseguimos uma taxa baixa para você.") is True


def test_c_guaranteed_approval_is_still_a_promise() -> None:
    assert contains_forbidden_financial_promise("Seu financiamento está aprovado.") is True
    assert contains_financing_approval_claim("Seu financiamento está aprovado.") is True
    assert contains_forbidden_financial_promise("Você consegue financiar 100% com certeza.") is True


# ---------------------------------------------------------------------------
# D1–D12  financial promise propositions (possibility vs certainty)
# ---------------------------------------------------------------------------

def test_d1_requesting_simulation_without_down_payment_is_allowed() -> None:
    assert contains_forbidden_financial_promise("Pode solicitar simulação sem entrada") is False


def test_d2_possible_to_simulate_without_down_payment_is_allowed() -> None:
    assert contains_forbidden_financial_promise("É possível simular sem entrada") is False
    assert contains_forbidden_financial_promise(
        "Financiamento sem entrada pode ser possível, sujeito à análise de crédito."
    ) is False


def test_d3_lender_dependency_disclaimer_is_allowed() -> None:
    assert contains_forbidden_financial_promise("Taxa e prazo dependem da financeira") is False


def test_d4_asserted_100_percent_financing_is_forbidden() -> None:
    assert contains_forbidden_financial_promise("Financiamos 100%") is True
    assert contains_forbidden_financial_promise("Financiamos 100% do veículo.") is True
    assert contains_financing_approval_claim("Financiamos 100% do veículo.") is True


def test_d5_capability_claim_of_100_percent_financing_is_forbidden() -> None:
    assert contains_forbidden_financial_promise("Você consegue financiar 100%") is True
    assert contains_forbidden_financial_promise("Você consegue financiar 100%.") is True
    assert contains_financing_approval_claim("Você consegue financiar 100%.") is True


def test_d6_unhedged_full_value_financing_is_forbidden() -> None:
    assert contains_forbidden_financial_promise("Dá para financiar todo o valor.") is True
    assert contains_forbidden_financial_promise("Dá pra financiar o valor todo.") is True
    assert contains_financing_approval_claim("Dá para financiar todo o valor.") is True


def test_d7_lender_may_analyze_integral_financing_is_allowed() -> None:
    assert (
        contains_forbidden_financial_promise(
            "A financeira pode analisar financiamento do valor integral"
        )
        is False
    )
    assert (
        contains_forbidden_financial_promise(
            "A financeira pode analisar um financiamento integral, sujeito à análise de crédito."
        )
        is False
    )


def test_d8_unauthorized_numeric_rate_is_forbidden() -> None:
    assert contains_forbidden_financial_promise("Taxa de 1,5%") is True
    assert contains_forbidden_financial_promise("A taxa será de 1,49% ao mês.") is True


def test_d9_promised_final_installment_is_forbidden() -> None:
    assert contains_forbidden_financial_promise("Sua parcela ficará em R$ 1.500") is True
    assert contains_forbidden_financial_promise("Sua parcela ficará em R$ 1.500.") is True


def test_d10_echoed_desired_installment_is_allowed() -> None:
    assert contains_forbidden_financial_promise("Você busca parcela em torno de R$ 1.500") is False
    assert contains_forbidden_financial_promise(
        "Entendi, você busca uma parcela por volta de R$ 1.500."
    ) is False


def test_d11_financing_approved_as_certain_is_forbidden() -> None:
    assert contains_forbidden_financial_promise("Seu financiamento está aprovado") is True
    assert contains_financing_approval_claim("Seu financiamento está aprovado") is True
    assert contains_forbidden_financial_promise("O banco aprova sem entrada.") is True
    assert contains_financing_approval_claim("O banco aprova sem entrada.") is True


def test_d12_condition_and_promise_are_not_confused_by_substring() -> None:
    """Isolated 'taxa' in a lender disclaimer is not a numeric-rate promise."""
    assert contains_forbidden_financial_promise(SAFE_TAXA_DISCLAIMER) is False
    for pattern in _FORBIDDEN_PROMISE_PATTERNS:
        assert pattern.search(SAFE_TAXA_DISCLAIMER) is None, pattern.pattern
    assert contains_forbidden_financial_promise("A taxa será de 1,5%.") is True
    mixed = f"{SAFE_TAXA_DISCLAIMER} A taxa será de 1,5%."
    assert contains_forbidden_financial_promise(mixed) is True
    assert contains_forbidden_financial_promise(
        "A taxa e o prazo dependem da análise da financeira."
    ) is False
    # A trailing lender hedge does not turn an asserted outcome into a process.
    assert contains_forbidden_financial_promise(
        "Financiamos 100% sujeito à análise da financeira."
    ) is True


# ---------------------------------------------------------------------------
# D–E  greeting / model already known
# ---------------------------------------------------------------------------

def test_d_neutral_greeting_does_not_assume_customer_owns_a_vehicle() -> None:
    bubbles = introduction_smalltalk_bubbles(
        "pt-BR",
        customer_name="Carla Mendes",
        inbound_text="Tudo bem?",
    )
    joined = " ".join(bubbles).lower()
    assert "seu veículo" not in joined
    assert "com o veículo" not in joined
    assert "com esse veículo" not in joined
    assert "júlia" in joined or "julia" in joined
    objective = response_objective_for(action=Action.SMALLTALK, should_introduce=True).lower()
    assert "seu veículo" not in objective
    assert "com o veículo" not in objective


def test_e_known_model_does_not_get_empty_praise_or_generic_menu() -> None:
    plan = build_dialogue_plan(
        inbound_text="Quero mais informações da Strada.",
        action=Action.SHOW_OFFERS,
        intent=BusinessIntent.PURCHASE,
        should_introduce=True,
        facts_context={"desired_model": "Strada"},
    )
    assert plan.skip_generic_intent_menu is True
    cleaned, result = validate_dialogue_plan(
        ["A Strada é uma excelente opção. Quer comprar, trocar, vender, consignar ou refinanciar?"],
        plan,
        should_introduce=True,
    )
    assert result["pass"] is False
    violations = set(result.get("violations") or [])
    assert "empty_vehicle_praise" in violations or "generic_menu_when_intent_known" in violations
    joined = " ".join(cleaned).lower()
    assert "excelente opção" not in joined


# ---------------------------------------------------------------------------
# F–H  primary vehicle label
# ---------------------------------------------------------------------------

def test_f_primary_vehicle_uses_catalog_label() -> None:
    load_seed()
    label = conversational_label_for_id("VH-STRADA-2018")
    assert label is not None
    assert "Strada" in label
    assert "2018" in label
    assert "Freedom" in label
    fox = conversational_label_for_id("VH-FOX-2014-001")
    assert fox is not None
    assert "Fox" in fox
    assert "2014" in fox
    assert "1.6" in fox


def test_g_absence_of_primary_does_not_pick_first_shown() -> None:
    load_seed()
    state = _financing_ready(
        primary_vehicle_id=None,
        photo_request=True,
        last_shown_vehicle_ids=["VH-STRADA-2021", "VH-STRADA-2017", "VH-STRADA-2018"],
    )
    plan = decide(state)
    if plan.action == Action.SEND_PHOTOS:
        vehicle_id = (plan.tool_calls[0] or {}).get("vehicle_id")
        assert vehicle_id != "VH-STRADA-2021"
    label = conversational_label_for_id(state.primary_vehicle_id) if state.primary_vehicle_id else None
    assert label is None
    summary = compose_vendor_summary(state).text
    assert "Freedom 1.3 2021" not in summary
    assert "VH-STRADA-2021" not in summary


def test_h_vendor_summary_identifies_unequivocal_primary() -> None:
    load_seed()
    state = _financing_ready(
        primary_vehicle_id="VH-STRADA-2018",
        facts={"document_status": {"cnh": "received"}},
    )
    text = compose_vendor_summary(state).text
    assert "2018" in text
    assert "Strada" in text
    assert "Freedom" in text or "1.4" in text
    assert not text.rstrip(".").endswith("Fiat Strada")


# ---------------------------------------------------------------------------
# I  installment acknowledgment
# ---------------------------------------------------------------------------

def test_i_installment_ack_rejects_artificial_celebration() -> None:
    plan = build_dialogue_plan(
        inbound_text="Parcela de uns 1500",
        action=Action.ASK_INFO,
        ask_field="documents",
        intent=BusinessIntent.PURCHASE_FINANCING,
        ack_kind="desired_installment",
        facts_context={"desired_installment": 1500, "desired_model": "Strada"},
        state=_financing_ready(),
    )
    assert "desired_installment" in plan.facts_to_acknowledge
    cleaned, result = validate_dialogue_plan(
        ["Legal sobre a parcela de uns 1500! Pode me enviar a CNH?"],
        plan,
    )
    assert result["pass"] is False
    assert "artificial_acknowledgment" in (result.get("violations") or [])
    ok, ok_result = validate_dialogue_plan(
        ["Entendi, você busca uma parcela por volta de R$ 1.500. Se conseguir, envie a CNH."],
        plan,
    )
    assert ok_result["pass"] is True
    assert "r$ 1.500" in " ".join(ok).lower()


# ---------------------------------------------------------------------------
# J–T  documents, visit, enrichment, handoff independence
# ---------------------------------------------------------------------------

def test_j_partial_cnh_is_documentary_action_only() -> None:
    state = _financing_ready(
        document_received=True,
        facts={"document_status": {"cnh": "received"}},
    )
    plan = decide(state)
    assert plan.action == Action.ASK_INFO
    assert plan.ask_field == "documents"
    assert plan.primary_action == PRIMARY_ASK_REMAINING_DOCUMENTS
    assert ACT_INVITE_VISIT in (plan.forbidden_concurrent_actions or [])
    assert remaining_document_components(state) == ["proof_of_residence", "proof_of_income"]


def test_k_remaining_documents_are_asked_once() -> None:
    state = _financing_ready(
        document_received=True,
        remaining_documents_asked=True,
        facts={"document_status": {"cnh": "received"}},
    )
    assert should_ask_remaining_documents(state) is False
    plan = decide(state)
    assert plan.ask_field != "documents"


def test_l_cnh_plus_bring_rest_to_store_does_not_insist_on_documents() -> None:
    parsed = parse_document_deferral("Recebi. Levo o resto na loja")
    assert parsed.get("proof_of_residence") == "deferred"
    assert parsed.get("proof_of_income") == "deferred"
    prev = _financing_ready(
        facts={"document_status": {"cnh": "received"}},
    )
    merged = deterministic_merge(
        prev,
        TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, facts={"documents_deferred": True}),
        inbound_text="Levo o resto na loja",
    )
    merged = refresh_actionability(merged)
    assert merged.facts.get("document_status", {}).get("cnh") == "received"
    assert "proof_of_residence" in (merged.deferred_fields or [])
    plan = decide(merged)
    assert plan.ask_field != "documents"


def test_m_unavailable_documents_defer_without_blocking_handoff() -> None:
    parsed = parse_document_deferral("Não estou com os documentos agora")
    assert parsed.get("cnh") == "deferred"
    assert parsed.get("proof_of_income") == "deferred"
    state = _financing_ready(
        deferred_fields=["cnh", "proof_of_residence", "proof_of_income"],
        facts={
            "documents_deferred": True,
            "document_status": {
                "cnh": "deferred",
                "proof_of_residence": "deferred",
                "proof_of_income": "deferred",
            },
        },
    )
    assert state.handoff_ready is True
    assert state.profile_complete is False
    plan = decide(state)
    assert plan.ask_field != "documents"


def test_n_vendor_request_prevails_over_documents() -> None:
    state = _financing_ready(
        document_received=True,
        signals=HandoffSignals(explicit_handoff=True),
        facts={"document_status": {"cnh": "received"}},
    )
    plan = decide(state)
    assert plan.action == Action.HANDOFF_VENDOR
    assert plan.ask_field != "documents"


def test_o_visit_prevails_over_documents() -> None:
    state = _financing_ready(
        document_received=True,
        signals=HandoffSignals(visit_intent=True),
        facts={"document_status": {"cnh": "received"}},
    )
    plan = decide(state)
    assert plan.action in {Action.REGISTER_VISIT_INTEREST, Action.HANDOFF_VENDOR}
    assert plan.ask_field != "documents"


def test_p_cash_payment_removes_documentary_applicability() -> None:
    state = _financing_ready(facts={"payment_method": "cash"})
    assert financing_documents_applicable(state) is False
    assert field_is_applicable(state, "documents") is False
    assert next_ask_field(state) != "documents"


def test_q_field_extracted_from_document_is_not_reasked() -> None:
    state = _financing_ready(
        document_received=True,
        facts={"document_status": {"cnh": "received"}, "name": "Bruno Azevedo"},
    )
    assert next_ask_field(state) != "name"
    plan = decide(state)
    assert plan.ask_field != "name"


def test_r_handoff_ready_can_coexist_with_incomplete_profile() -> None:
    state = _financing_ready(facts={"document_status": {"cnh": "received"}})
    assert state.handoff_ready is True
    assert state.profile_complete is False
    assert "proof_of_residence" in state.missing_fields


def test_s_enrichment_does_not_exceed_limit() -> None:
    state = _financing_ready(
        document_received=True,
        enrichment_ask_count=ENRICHMENT_ASK_LIMIT,
        facts={"document_status": {"cnh": "received"}},
    )
    assert should_ask_remaining_documents(state) is False
    plan = decide(state)
    assert plan.ask_field != "documents"
    assert plan.action in {Action.REGISTER_VISIT_INTEREST, Action.HANDOFF_VENDOR}


def test_t_one_reply_does_not_combine_remaining_docs_and_visit() -> None:
    state = _financing_ready(
        document_received=True,
        facts={"document_status": {"cnh": "received"}},
    )
    plan = decide(state)
    dialogue = build_dialogue_plan(
        inbound_text="Segue a CNH",
        action=plan.action,
        ask_field=plan.ask_field,
        intent=state.intent,
        ack_kind="document_received",
        inbound_content_type="DOCUMENT",
        document_kind="CNH",
        state=state,
        reason_code=plan.reason_code,
    )
    assert DialogueAct.INVITE_VISIT.value not in dialogue.acts
    assert dialogue.primary_action == PRIMARY_ASK_REMAINING_DOCUMENTS
    cleaned, result = validate_dialogue_plan(
        [
            "Recebi sua CNH, Bruno.",
            "Se conseguir, envie também os comprovantes de renda e residência.",
            "Você pode vir amanhã às 9h30?",
        ],
        dialogue,
        document_kind="CNH",
    )
    assert result["pass"] is False
    assert "concurrent_actions" in (result.get("violations") or [])
    joined = " ".join(cleaned).lower()
    asks_docs = "renda" in joined or "residência" in joined or "residencia" in joined
    asks_visit = "9h30" in joined or "visita" in joined or "amanhã" in joined
    assert not (asks_docs and asks_visit)


def test_received_cnh_is_not_claimed_deferred_in_mixed_summary() -> None:
    from sdr.domain.summary_propositions import detect_claims

    text = (
        "A CNH já foi recebida. O comprovante de renda e o comprovante de "
        "residência ficaram para envio posterior."
    )
    auth = {
        "document_status": {
            "cnh": "received",
            "proof_of_income": "deferred",
            "proof_of_residence": "deferred",
        }
    }
    claims = detect_claims(text, auth)
    deferred_cnh = [
        item
        for item in claims
        if item.get("entity") == "documents"
        and item.get("attribute") == "cnh"
        and item.get("value") == "deferred"
    ]
    assert not deferred_cnh
    deferred_income = [
        item
        for item in claims
        if item.get("attribute") == "proof_of_income" and item.get("value") == "deferred"
    ]
    assert deferred_income


def test_phase9_microscenario_catalog_is_complete() -> None:
    from sdr.gate_phase9 import REPEAT_THREE, list_phase9_scenarios

    names = [path.stem for path in list_phase9_scenarios()]
    assert len(names) == 15
    assert names[0] == "p9_01_cumprimento_puro"
    assert names[-1] == "p9_15_item_sem_informacao_segura"
    assert set(REPEAT_THREE) <= set(names)
    assert len(REPEAT_THREE) == 6


def test_register_catalog_id_index_does_not_invent_fields() -> None:
    register_catalog_vehicles(
        [{"id": "VH-X", "brand": "Honda", "model": "Civic", "version": "EXL", "year": 2020}]
    )
    assert conversational_label_for_id("VH-X") == "Civic EXL 2020"
    assert conversational_label_for_id("VH-MISSING") is None
