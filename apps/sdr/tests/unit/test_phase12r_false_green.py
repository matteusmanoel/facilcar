"""Phase 12R — false-green classes: documents vs visit, CNH action, summary, adapter."""

from __future__ import annotations

import pytest

from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.document_commitment import (
    COMMITMENT_CLAIM_UNAVAILABLE,
    commitment_claim_for_inbound,
    inbound_states_documents_unavailable,
)
from sdr.domain.document_status import parse_document_deferral
from sdr.domain.followup import enrich_turn_facts_from_inbound, followup_decision, inbound_looks_like_visit
from sdr.domain.visit import explicit_in_person_visit
from sdr.domain.merge import deterministic_merge
from sdr.domain.qualification_policy import (
    remaining_document_components,
    should_ask_remaining_documents,
)
from sdr.domain.qualifications import refresh_actionability
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
    TurnFacts,
)
from sdr.domain.vendor_summary import compose_vendor_summary
from sdr.infrastructure.isolated_crm import IsolatedCrmStore
from sdr.infrastructure.isolated_inventory import IsolatedInventoryAdapter, coerce_isolated_pool


def _financing_ready(**kwargs) -> ConversationCanonicalState:
    facts = {
        "desired_model": "Civic",
        "desired_vehicle_text": "Civic",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 1500,
        "name": "Carla Mendes",
        **kwargs.pop("facts", {}),
    }
    state = ConversationCanonicalState(
        thread_id="t-12r",
        customer=CustomerState(phone="5511988001100", name="Carla Mendes"),
        intent=kwargs.pop("intent", BusinessIntent.PURCHASE_FINANCING),
        language="pt-BR",
        facts=facts,
        last_inventory_search_key=inventory_search_key(facts),
        last_shown_vehicle_ids=kwargs.pop("last_shown_vehicle_ids", ["VH-CIVIC-2020"]),
        documents_asked=True,
        installment_asked=True,
    )
    for key, value in kwargs.items():
        setattr(state, key, value)
    return refresh_actionability(state)


def _merge_unavailable(text: str, **kwargs) -> ConversationCanonicalState:
    prev = _financing_ready(**kwargs)
    facts = TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, facts={})
    enrich_turn_facts_from_inbound(facts, text)
    return refresh_actionability(deterministic_merge(prev, facts, inbound_text=text))


UNAVAILABLE_PHRASES = (
    "Não estou com os documentos agora.",
    "Não tenho os comprovantes em mãos.",
    "Estou sem a documentação no momento.",
    "Depois eu vejo os documentos.",
)


def test_a_isolated_document_unavailability_is_not_visit() -> None:
    for inbound in UNAVAILABLE_PHRASES:
        assert inbound_states_documents_unavailable(inbound)
        assert commitment_claim_for_inbound(inbound) == COMMITMENT_CLAIM_UNAVAILABLE
        assert inbound_looks_like_visit(inbound) is False
        state = _merge_unavailable(inbound)
        assert state.facts.get("documents_deferred") is True
        assert state.visit_preferred_time is None
        plan = decide(state)
        tools = [str((tc or {}).get("tool") or "") for tc in (plan.tool_calls or [])]
        assert plan.action != Action.REGISTER_VISIT_INTEREST, inbound
        assert "register_visit_interest" not in tools, inbound
        decision = followup_decision(state, TurnFacts(intent=state.intent), inbound_text=inbound)
        assert decision.eligible is False, inbound


def test_b_callback_with_unavailability_is_followup_not_visit() -> None:
    inbound = "Não estou com os documentos agora. Pode me chamar amanhã."
    state = _merge_unavailable(inbound)
    plan = decide(state)
    tools = [str((tc or {}).get("tool") or "") for tc in (plan.tool_calls or [])]
    assert plan.action != Action.REGISTER_VISIT_INTEREST
    assert "register_visit_interest" not in tools
    facts = TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING)
    enrich_turn_facts_from_inbound(facts, inbound)
    decision = followup_decision(state, facts, inbound_text=inbound)
    assert decision.eligible is True
    assert decision.schedule_at is not None


def test_c_explicit_visit_stays_separate_from_document_deferral() -> None:
    inbound = "Não estou com os documentos agora. Posso ir à loja amanhã?"
    assert inbound_states_documents_unavailable(inbound)
    assert inbound_looks_like_visit(inbound)
    assert explicit_in_person_visit(inbound)
    parsed = parse_document_deferral(inbound)
    assert parsed.get("cnh") == "deferred"
    prev = _financing_ready()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"documents_deferred": True},
        signals=HandoffSignals(visit_intent=True),
    )
    enrich_turn_facts_from_inbound(facts, inbound)
    state = refresh_actionability(deterministic_merge(prev, facts, inbound_text=inbound))
    assert state.facts.get("documents_deferred") is True
    plan = decide(state)
    assert plan.action == Action.REGISTER_VISIT_INTEREST
    status = state.facts.get("document_status") or {}
    assert status.get("cnh") != "received"
    assert status.get("proof_of_income") != "received"


def test_d_cnh_only_asks_remaining_documents_once() -> None:
    state = _financing_ready(
        document_received=True,
        facts={"document_status": {"cnh": "received"}, "name": "Carla Mendes"},
    )
    assert remaining_document_components(state)
    assert should_ask_remaining_documents(state) is True
    plan = decide(state)
    assert plan.action == Action.ASK_INFO
    assert plan.ask_field == "documents"
    assert plan.reason_code == "remaining_documents"
    assert plan.primary_action == "ask_remaining_documents"
    tools = [str((tc or {}).get("tool") or "") for tc in (plan.tool_calls or [])]
    assert "register_visit_interest" not in tools


def test_e_actionable_cnh_does_not_block_or_duplicate_handoff() -> None:
    state = _financing_ready(
        document_received=True,
        vendor_notified_at="2026-09-07T10:00:00-03:00",
        facts={"document_status": {"cnh": "received"}},
    )
    assert state.handoff_ready is True
    plan = decide(state)
    assert plan.action != Action.REGISTER_VISIT_INTEREST
    assert plan.ask_field == "documents"
    assert plan.handoff is False
    assert plan.action != Action.HANDOFF_VENDOR


def test_f_complete_pack_does_not_reask_documents() -> None:
    state = _financing_ready(
        document_received=True,
        remaining_documents_asked=True,
        facts={
            "document_status": {
                "cnh": "received",
                "proof_of_income": "received",
                "proof_of_residence": "received",
            }
        },
    )
    assert remaining_document_components(state) == []
    plan = decide(state)
    assert plan.ask_field != "documents"


def test_g_explicit_vendor_prevails_after_cnh() -> None:
    state = _financing_ready(
        document_received=True,
        signals=HandoffSignals(explicit_handoff=True),
        facts={"document_status": {"cnh": "received"}},
    )
    plan = decide(state)
    assert plan.action == Action.HANDOFF_VENDOR
    assert plan.ask_field != "documents"


def test_h_explicit_visit_prevails_without_corrupting_cnh() -> None:
    state = _financing_ready(
        document_received=True,
        signals=HandoffSignals(visit_intent=True),
        facts={"document_status": {"cnh": "received"}},
    )
    plan = decide(state)
    assert plan.action == Action.REGISTER_VISIT_INTEREST
    assert state.facts.get("document_status", {}).get("cnh") == "received"
    assert state.facts.get("document_status", {}).get("proof_of_income") != "received"


def test_i_summary_after_resume_keeps_consolidated_civic() -> None:
    state = _financing_ready()
    store = IsolatedCrmStore()
    first = store.persist_handoff(state, first_inbound="Pode me passar para um vendedor?")
    lead_id = str(first["id"])
    state.active_lead_ids = [lead_id]
    state.facts["desired_model"] = "Civic"
    state.customer.name = "Carla Mendes"
    state.crm_revision = 2
    stored = store.sync_from_state(lead_id, state, qualify=False, first_inbound="Pode me passar para um vendedor?")
    reread = store.reread_id(lead_id)
    summary = compose_vendor_summary(state).text
    assert "Civic" in summary
    assert "Carla" in summary
    assert "Civic" in (stored.get("juliaSummary") or "")
    assert reread is not None
    assert reread.get("id") == lead_id
    assert "Civic" in (reread.get("juliaSummary") or summary)


def test_j_superseded_vehicle_replaces_previous_summary_fact() -> None:
    prev = _financing_ready()
    facts = TurnFacts(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts={"desired_model": "Fit", "desired_vehicle_text": "Fit"},
    )
    state = refresh_actionability(
        deterministic_merge(prev, facts, inbound_text="Na verdade quero o Fit")
    )
    summary = compose_vendor_summary(state).text
    assert "Fit" in summary
    assert "Civic" not in summary


@pytest.mark.asyncio
async def test_k_isolated_inventory_adapter_has_acquire_protocol() -> None:
    from sdr.domain.inventory_search import InventorySearchRequest
    from sdr.tools.inventory import search_with_request

    dummy = object()
    pool = coerce_isolated_pool(dummy)
    assert isinstance(pool, IsolatedInventoryAdapter)
    assert hasattr(pool, "acquire")
    req = InventorySearchRequest(original_model="Civic", limit=3)
    rows = await search_with_request(pool, req)
    assert rows == []
    async with pool.acquire() as conn:
        fetched = await conn.fetch("SELECT 1")
        assert fetched == []


def test_substitution_is_not_visit_evidence() -> None:
    inbound = "quero o Civic em vez de Corolla"
    assert inbound_looks_like_visit(inbound) is True
    assert explicit_in_person_visit(inbound) is False
    state = _merge_unavailable(inbound)
    assert state.visit_interest is False
    assert state.signals.visit_intent is not True
    assert state.facts.get("documents_deferred") is not True


def test_bare_nao_tenho_is_not_document_unavailability() -> None:
    inbound = "Não tenho entrada"
    assert inbound_states_documents_unavailable(inbound) is False
    assert parse_document_deferral(inbound) == {}
    state = _merge_unavailable(inbound)
    assert state.documents_unavailable_this_turn is False
    assert state.facts.get("documents_deferred") is not True


def test_depois_eu_vejo_requires_document_object() -> None:
    assert inbound_states_documents_unavailable("Depois eu vejo os documentos.")
    assert inbound_states_documents_unavailable("depois eu vejo o Civic") is False
    assert parse_document_deferral("depois eu vejo o Civic") == {}


def test_bring_remainder_to_store_is_explicit_visit_not_inferred() -> None:
    inbound = "Levo o restante na loja"
    assert explicit_in_person_visit(inbound)
    prev = _financing_ready(
        document_received=True,
        facts={"document_status": {"cnh": "received"}, "name": "Carla Mendes"},
    )
    facts = TurnFacts(intent=BusinessIntent.PURCHASE_FINANCING, facts={"documents_deferred": True})
    state = refresh_actionability(deterministic_merge(prev, facts, inbound_text=inbound))
    assert state.visit_interest is True
    assert state.facts.get("document_status", {}).get("cnh") == "received"
    assert state.facts.get("document_status", {}).get("proof_of_income") != "received"
    plan = decide(state)
    assert plan.action == Action.REGISTER_VISIT_INTEREST
