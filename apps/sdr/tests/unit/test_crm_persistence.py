"""Phase 5 — persist final commercial state into the CRM (tests A–Q)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from sdr.domain.clock import set_clock
from sdr.domain.commercial_snapshot import (
    DESIRED_INSTALLMENTS_IS_MONTH_COUNT,
    build_commercial_snapshot,
    monthly_payment_from_facts,
)
from sdr.domain.types import (
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    LifecycleState,
    LifecycleStatus,
)
from sdr.domain.vendor_summary import compose_vendor_summary
from sdr.infrastructure.isolated_crm import IsolatedCrmStore
from sdr.infrastructure.lead_repository import LeadRepository

STRADA_2021 = "veh-strada-2021"
STRADA_2017 = "veh-strada-2017"
STRADA_2018 = "veh-strada-2018"
FIRST_INBOUND = "Oi, vi as Stradas de vocês"


def setup_function() -> None:
    set_clock("2026-09-08T10:00:00-03:00")


def teardown_function() -> None:
    set_clock(None)


def _strada_state(**kwargs) -> ConversationCanonicalState:
    facts = {
        "name": "Mateus Manoel Ferreira",
        "desired_model": "Strada Working Hard",
        "desired_vehicle": {
            "brand": "Fiat",
            "model": "Strada Working Hard",
            "year": 2018,
        },
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 1500,
        "birth_date": "08/09/1994",
        "document_status": {
            "cnh": "received",
            "proof_of_income": "missing",
            "proof_of_residence": "missing",
        },
        "document_storage": {"cnh": {"status": "PENDING"}},
    }
    facts.update(kwargs.pop("facts", {}))
    defaults = dict(
        thread_id="thread-strada",
        customer=CustomerState(phone="5511999990000", name="Mateus Manoel Ferreira"),
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        last_shown_vehicle_ids=[STRADA_2021, STRADA_2017, STRADA_2018],
        primary_vehicle_id=STRADA_2018,
        visit_interest=True,
        visit_date="2026-09-08",
        visit_time="09:30",
        visit_preferred_time="terça-feira, 8/09, às 9h30",
        visit_raw="terça às 9h30",
        missing_fields=["proof_of_income", "proof_of_residence"],
        crm_revision=1,
    )
    defaults.update(kwargs)
    return ConversationCanonicalState(**defaults)


def test_a_same_lead_created_then_qualified() -> None:
    store = IsolatedCrmStore()
    early = _strada_state(crm_revision=1)
    early.facts = {"name": "Mateus Manoel Ferreira", "desired_model": "Strada"}
    early.primary_vehicle_id = None
    created = store.create_from_state(early, first_inbound=FIRST_INBOUND)
    early.active_lead_ids = [created["id"]]
    final = _strada_state(crm_revision=2)
    updated = store.sync_from_state(created["id"], final, qualify=True, first_inbound=FIRST_INBOUND)
    assert updated["id"] == created["id"]
    assert created["status"] == "NEW"
    assert updated["status"] == "QUALIFIED"
    assert "Working Hard" in updated["juliaSummary"] or "2018" in updated["juliaSummary"]
    assert updated["juliaSummary"] != created["juliaSummary"]


def test_b_strada_full_persist_and_reread() -> None:
    store = IsolatedCrmStore()
    state = _strada_state(crm_revision=1)
    created = store.create_from_state(state, first_inbound=FIRST_INBOUND)
    rec = store.sync_from_state(created["id"], state, qualify=True, first_inbound=FIRST_INBOUND)
    reread = store.reread_id(created["id"])
    assert reread is not None
    assert rec["id"] == reread["id"]
    interests = reread["vehicleInterests"]
    assert {i["vehicleId"] for i in interests} == {STRADA_2021, STRADA_2017, STRADA_2018}
    primary = [i for i in interests if i["isPrimary"]]
    assert len(primary) == 1
    assert primary[0]["vehicleId"] == STRADA_2018
    assert reread["vehicleId"] == STRADA_2018
    fin = reread["financingRequest"]
    assert fin["desiredMonthlyPayment"] == 1500
    assert fin["desiredInstallments"] is None
    assert fin["downPayment"] == 0
    docs = {d["component"]: d for d in reread["documents"]}
    assert docs["cnh"]["commerciallyReceived"] is True
    assert docs["cnh"]["downloadable"] is False
    visit = reread["visitInterest"]
    assert visit["preferredDate"] == "2026-09-08"
    assert visit["preferredTime"] == "09:30"
    summary = reread["juliaSummary"].lower()
    assert "2018" in summary
    assert "1.500" in reread["juliaSummary"] or "1500" in summary
    assert "cnh" in summary
    assert "9h30" in summary or "09:30" in summary


def test_c_primary_independent_of_interest_order() -> None:
    shuffled = _strada_state(
        last_shown_vehicle_ids=[STRADA_2018, STRADA_2021, STRADA_2017],
        crm_revision=1,
    )
    snap = build_commercial_snapshot(shuffled)
    assert snap.primary_vehicle_id == STRADA_2018
    store = IsolatedCrmStore()
    rec = store.create_from_state(shuffled)
    rec = store.sync_from_state(rec["id"], shuffled, qualify=True)
    badges = [i["isPrimary"] for i in rec["vehicleInterests"] if i["vehicleId"] == STRADA_2018]
    assert badges == [True]
    assert rec["juliaSummary"].count("2018") >= 1


def test_d_no_explicit_primary_does_not_pick_first() -> None:
    state = _strada_state(primary_vehicle_id=None, crm_revision=1)
    state.facts = {
        "name": "Mateus",
        "desired_model": "Strada",
        "payment_method": "financing",
        "down_payment": 0,
    }
    snap = build_commercial_snapshot(state)
    assert snap.primary_vehicle_id is None
    store = IsolatedCrmStore()
    created = store.create_from_state(state)
    rec = store.sync_from_state(created["id"], state, qualify=True)
    assert rec["vehicleId"] is None
    assert all(not i["isPrimary"] for i in rec["vehicleInterests"])
    assert "working hard" not in rec["juliaSummary"].lower()
    assert "2018" not in rec["juliaSummary"]


def test_e_monthly_amount_maps_to_money_field() -> None:
    snap = build_commercial_snapshot(_strada_state())
    assert snap.financing is not None
    assert snap.financing.desired_monthly_payment == 1500.0
    assert "1.500" in snap.julia_summary or "1500" in snap.julia_summary


def test_f_desired_installments_is_month_count_not_reais() -> None:
    assert DESIRED_INSTALLMENTS_IS_MONTH_COUNT is True
    amount = monthly_payment_from_facts({"desired_installment": 1500})
    snap = build_commercial_snapshot(_strada_state())
    assert amount == 1500
    assert snap.financing is not None
    assert snap.financing.desired_installments_count is None
    assert snap.financing.desired_monthly_payment == 1500


def test_h_cnh_received_storage_pending_not_downloadable() -> None:
    snap = build_commercial_snapshot(_strada_state())
    cnh = next(d for d in snap.documents if d.component == "cnh")
    assert cnh.commercially_received is True
    assert cnh.downloadable is False
    low = snap.julia_summary.lower()
    assert "cnh" in low
    assert "download" not in low
    assert "disponível para download" not in low


def test_i_post_handoff_visit_updates_same_lead() -> None:
    store = IsolatedCrmStore()
    first = _strada_state(crm_revision=1)
    first.visit_time = None
    first.visit_preferred_time = "terça-feira, 8/09"
    created = store.create_from_state(first, first_inbound=FIRST_INBOUND)
    store.sync_from_state(created["id"], first, qualify=True)
    assert store.handoff_count == 1
    later = _strada_state(crm_revision=2)
    later.lifecycle = LifecycleState(status=LifecycleStatus.HANDOFF_SENT)
    updated = store.sync_from_state(created["id"], later, qualify=False)
    assert updated["id"] == created["id"]
    assert updated["status"] == "QUALIFIED"
    assert updated["visitInterest"]["preferredTime"] == "09:30"
    assert "9h30" in updated["juliaSummary"]
    assert store.handoff_count == 1
    assert store.qualified_notifications == 1


def test_j_generic_summary_replaced_by_final() -> None:
    store = IsolatedCrmStore()
    early = _strada_state(crm_revision=1)
    early.facts = {"name": "Mateus Manoel Ferreira", "desired_model": "Strada"}
    early.primary_vehicle_id = None
    created = store.create_from_state(early, first_inbound=FIRST_INBOUND)
    generic = created["juliaSummary"]
    final = store.sync_from_state(created["id"], _strada_state(crm_revision=2), qualify=True)
    assert final["juliaSummary"] != generic
    assert "2018" in final["juliaSummary"]


def test_k_original_message_is_first_inbound() -> None:
    snap = build_commercial_snapshot(_strada_state(), first_inbound=FIRST_INBOUND)
    assert snap.original_message == FIRST_INBOUND
    assert snap.original_message != snap.julia_summary
    store = IsolatedCrmStore()
    rec = store.create_from_state(_strada_state(), first_inbound=FIRST_INBOUND)
    rec = store.sync_from_state(rec["id"], _strada_state(crm_revision=2), qualify=True, first_inbound=FIRST_INBOUND)
    assert rec["message"] == FIRST_INBOUND
    assert rec["message"] != rec["juliaSummary"]


def test_l_retry_does_not_duplicate() -> None:
    store = IsolatedCrmStore()
    state = _strada_state(crm_revision=3)
    created = store.create_from_state(state, first_inbound=FIRST_INBOUND)
    store.sync_from_state(created["id"], state, qualify=True)
    store.sync_from_state(created["id"], state, qualify=True)
    rec = store.reread_id(created["id"])
    assert rec is not None
    assert len(store._by_id) == 1
    assert len(rec["vehicleInterests"]) == 3
    assert store.qualified_notifications == 1
    assert rec["financingRequest"]["desiredMonthlyPayment"] == 1500


def test_m_stale_revision_does_not_overwrite() -> None:
    store = IsolatedCrmStore()
    newer = _strada_state(crm_revision=5)
    created = store.create_from_state(newer, first_inbound=FIRST_INBOUND)
    store.sync_from_state(created["id"], newer, qualify=True)
    older = _strada_state(crm_revision=2)
    older.facts = {**older.facts, "desired_installment": 400}
    older.primary_vehicle_id = STRADA_2021
    rejected = store.sync_from_state(created["id"], older, qualify=True)
    assert rejected.get("stale_rejected") is True
    rec = store.reread_id(created["id"])
    assert rec is not None
    assert rec["financingRequest"]["desiredMonthlyPayment"] == 1500
    assert rec["vehicleId"] == STRADA_2018


def test_n_intents_persist_only_applicable_fields() -> None:
    sale = ConversationCanonicalState(
        thread_id="t-sale",
        customer=CustomerState(phone="1", name="Bruno"),
        intent=BusinessIntent.SALE,
        facts={"trade_model": "Corolla", "trade_has_financing": False, "trade_has_debts": False},
        crm_revision=1,
    )
    sale_snap = build_commercial_snapshot(sale)
    assert sale_snap.financing is None
    assert sale_snap.sell is True
    assert "document" not in sale_snap.julia_summary.lower()

    cash = ConversationCanonicalState(
        thread_id="t-cash",
        customer=CustomerState(phone="1", name="Lucas"),
        intent=BusinessIntent.PURCHASE,
        facts={"desired_model": "Onix", "payment_method": "cash"},
        crm_revision=1,
    )
    cash_snap = build_commercial_snapshot(cash)
    assert cash_snap.financing is None
    assert "cnh" not in cash_snap.julia_summary.lower()


def test_o_summary_factuality() -> None:
    text = compose_vendor_summary(_strada_state()).text.lower()
    assert "aprovad" not in text
    assert "marcada" not in text
    assert "agendada" not in text
    assert "download" not in text
    assert "avalia" not in text
    assert "quitado" not in text
    assert "sem débitos" not in text and "sem debitos" not in text


def test_p_handoff_only_qualifies() -> None:
    store = IsolatedCrmStore()
    created = store.create_from_state(_strada_state(crm_revision=1))
    assert created["status"] == "NEW"
    mid = store.sync_from_state(created["id"], _strada_state(crm_revision=2), qualify=False)
    assert mid["status"] == "NEW"
    done = store.sync_from_state(created["id"], _strada_state(crm_revision=3), qualify=True)
    assert done["status"] == "QUALIFIED"
    assert done["status"] not in {"CONTACTED", "WON", "LOST", "IN_PROGRESS"}


@pytest.mark.asyncio
async def test_f_sql_never_writes_monthly_amount_to_desired_installments() -> None:
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock())
    )
    repo = LeadRepository(pool)
    await repo._upsert_financing(conn, "lead-1", _strada_state())
    sql = conn.execute.await_args.args[0]
    args = conn.execute.await_args.args[1:]
    assert "desiredMonthlyPayment" in sql
    assert 1500 in args or 1500.0 in args
    # Month-count bind is None; 1500 must not sit in desiredInstallments position.
    assert args[-2] is None or args[-2] != 1500
