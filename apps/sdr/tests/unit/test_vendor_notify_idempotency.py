"""Vendor notify is dispatch evidence, not a mutable commercial status."""

from __future__ import annotations

import threading

import pytest

from sdr.domain.clock import set_clock
from sdr.domain.decision import decide
from sdr.domain.ownership import (
    confirm_vendor_dispatch,
    vendor_already_notified,
    vendor_notify_idempotency_key,
)
from sdr.domain.types import (
    Action,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    LifecycleState,
    LifecycleStatus,
)
from sdr.infrastructure.isolated_crm import IsolatedCrmStore


THREAD = "t-vendor-notify"
LEAD_PHONE = "5511988001100"


@pytest.fixture(autouse=True)
def _freeze_clock() -> None:
    set_clock("2026-09-08T16:00:00-03:00")
    yield
    set_clock(None)


def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id=kwargs.pop("thread_id", THREAD),
        customer=kwargs.pop(
            "customer",
            CustomerState(phone=LEAD_PHONE, name="Carla Mendes"),
        ),
        intent=kwargs.pop("intent", BusinessIntent.PURCHASE_FINANCING),
        facts=kwargs.pop("facts", {"desired_model": "Civic", "desired_installment": 1500}),
        lifecycle=kwargs.pop(
            "lifecycle",
            LifecycleState(status=LifecycleStatus.READY_FOR_HANDOFF),
        ),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_c1_qualified_status_without_dispatch_is_not_notified() -> None:
    state = _state(
        lifecycle=LifecycleState(status=LifecycleStatus.AI_RESUMED),
        active_lead_ids=["lead-qualified-no-dispatch"],
        handoff_at="2026-09-08T15:00:00-03:00",
    )
    store = IsolatedCrmStore()
    created = store.create_from_state(state)
    created_id = str(created["id"])
    store._by_id[created_id]["status"] = "QUALIFIED"
    store._records[state.thread_id]["status"] = "QUALIFIED"
    reread = store.reread_id(created_id)
    assert reread is not None
    assert reread["status"] == "QUALIFIED"
    assert reread.get("vendorNotifiedAt") is None
    assert vendor_already_notified(state) is False


def test_c2_confirmed_dispatch_sets_vendor_already_notified() -> None:
    state = _state()
    store = IsolatedCrmStore()
    stored = store.persist_handoff(state)
    assert stored["status"] == "QUALIFIED"
    assert stored.get("vendorNotifiedAt")
    assert vendor_already_notified(state) is True
    assert state.vendor_notified_at is not None
    assert vendor_notify_idempotency_key(state) == f"handoff:{THREAD}"


def test_c3_retry_after_confirmed_does_not_notify_twice() -> None:
    state = _state()
    store = IsolatedCrmStore()
    first = store.persist_handoff(state)
    state.facts = {**state.facts, "desired_installment": 1800}
    state.crm_revision = int(state.crm_revision or 0) + 1
    second = store.persist_handoff(state)
    assert second["id"] == first["id"]
    assert store.handoff_count == 1
    assert store.qualified_notifications == 1
    assert vendor_already_notified(state) is True
    plan = decide(state)
    assert plan.action != Action.HANDOFF_VENDOR
    assert plan.handoff is not True


def test_c4_failure_before_confirm_allows_retry() -> None:
    state = _state()
    store = IsolatedCrmStore()
    store.fail_before_confirm = True
    with pytest.raises(RuntimeError, match="confirmation failed"):
        store.persist_handoff(state)
    assert vendor_already_notified(state) is False
    assert store.handoff_count == 0
    reread = store.reread(state.thread_id)
    assert reread is not None
    assert reread["status"] == "QUALIFIED"
    assert reread.get("vendorNotifiedAt") is None

    store.fail_before_confirm = False
    stored = store.persist_handoff(state)
    assert stored["id"] == reread["id"]
    assert store.handoff_count == 1
    assert vendor_already_notified(state) is True


def test_c5_post_handoff_crm_update_does_not_notify_again() -> None:
    state = _state(crm_revision=1)
    store = IsolatedCrmStore()
    first = store.persist_handoff(state)
    later = _state(crm_revision=2, active_lead_ids=[first["id"]])
    later.facts = {**later.facts, "desired_installment": 1800}
    later.lifecycle = LifecycleState(status=LifecycleStatus.HANDOFF_SENT)
    later.vendor_notified_at = state.vendor_notified_at
    updated = store.sync_from_state(first["id"], later, qualify=False)
    assert updated["id"] == first["id"]
    assert store.handoff_count == 1
    assert store.qualified_notifications == 1
    assert vendor_already_notified(later) is True
    plan = decide(later)
    assert plan.action != Action.HANDOFF_VENDOR


def test_c6_manual_status_change_does_not_fake_confirmation() -> None:
    state = _state(lifecycle=LifecycleState(status=LifecycleStatus.BOT_ACTIVE))
    assert vendor_already_notified(state) is False
    state.lifecycle.status = LifecycleStatus.HANDOFF_SENT
    state.handoff_at = "2026-09-08T15:30:00-03:00"
    assert vendor_already_notified(state) is False
    state.lifecycle.status = LifecycleStatus.HUMAN_ACTIVE
    assert vendor_already_notified(state) is False
    state.lifecycle.status = LifecycleStatus.AI_RESUMED
    assert vendor_already_notified(state) is False
    store = IsolatedCrmStore()
    created = store.create_from_state(state)
    store._by_id[str(created["id"])]["status"] = "QUALIFIED"
    assert vendor_already_notified(state) is False
    confirm_vendor_dispatch(state)
    assert vendor_already_notified(state) is True


def test_c7_two_workers_notify_only_once() -> None:
    store = IsolatedCrmStore()
    errors: list[BaseException] = []
    ids: list[str] = []

    def worker() -> None:
        try:
            rec = store.persist_handoff(_state())
            ids.append(str(rec["id"]))
        except BaseException as exc:  # noqa: BLE001 — collect worker failures
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert store.handoff_count == 1
    assert store.qualified_notifications == 1
    assert len(set(ids)) == 1
    reread = store.reread(THREAD)
    assert reread is not None
    assert reread["id"] == ids[0]


def test_c8_same_event_reprocessed_notifies_once() -> None:
    state = _state()
    store = IsolatedCrmStore()
    first = store.persist_handoff(state)
    replayed = store.persist_handoff(state)
    assert replayed["id"] == first["id"]
    assert store.handoff_count == 1
    assert vendor_already_notified(state) is True
    plan = decide(state)
    assert plan.action != Action.HANDOFF_VENDOR
