"""D1–D12: contextual follow-up compose + validator (no live OpenAI, no sleep)."""

from __future__ import annotations

from datetime import datetime

import pytest

from sdr.domain.clock import GOLDEN_CLOCK_ISO, TZ_BRT, parse_clock, set_clock
from sdr.domain.followup_plan import (
    FollowUpAction,
    FollowUpPlan,
    FollowUpReason,
    FollowUpStrategy,
)
from sdr.domain.followup_validator import validate_followup
from sdr.domain.types import InventoryOutcome
from sdr.understanding.followup_composer import compose_followup


def setup_function() -> None:
    set_clock(GOLDEN_CLOCK_ISO)


def teardown_function() -> None:
    set_clock(None)


def _inventory(
    outcome: str,
    *,
    vehicles: list[dict] | None = None,
    alternatives: list[dict] | None = None,
    availability_status: str | None = None,
) -> list[dict]:
    payload: dict = {
        "tool": "inventory_search",
        "outcome": outcome,
        "vehicles": vehicles or [],
        "alternatives": alternatives or [],
        "count": len(vehicles or []),
    }
    if availability_status:
        payload["availability_status"] = availability_status
    return [payload]


def _plan_documents() -> FollowUpPlan:
    return FollowUpPlan(
        reason=FollowUpReason.DOCUMENTS_PENDING.value,
        requested_action=FollowUpAction.ASK_DOCUMENTS_STATUS.value,
        pending_commitment="send_proofs_later",
        authorized_facts={"pending_commitment": "send_proofs_later"},
    )


def _plan_partner(label: str = "Onix 2022") -> FollowUpPlan:
    return FollowUpPlan(
        reason=FollowUpReason.PARTNER_DECISION.value,
        requested_action=FollowUpAction.ASK_PARTNER_DECISION.value,
        vehicle_label=label,
        pending_commitment="talk_with_partner",
        authorized_facts={
            "vehicle_label": label,
            "pending_commitment": "talk_with_partner",
        },
    )


def _plan_simulation(label: str = "Civic 2020") -> FollowUpPlan:
    return FollowUpPlan(
        reason=FollowUpReason.INTERRUPTED_SIMULATION.value,
        requested_action=FollowUpAction.RESUME_SIMULATION.value,
        vehicle_label=label,
        pending_commitment="financing_simulation",
        authorized_facts={
            "vehicle_label": label,
            "pending_commitment": "financing_simulation",
        },
    )


def _plan_vehicle(label: str = "Tracker 2021") -> FollowUpPlan:
    return FollowUpPlan(
        reason=FollowUpReason.SPECIFIC_VEHICLE.value,
        requested_action=FollowUpAction.ASK_VEHICLE_INTEREST.value,
        vehicle_label=label,
        authorized_facts={"vehicle_label": label, "stock_snapshot": "available"},
    )


def _joined(bubbles: list[str]) -> str:
    return " ".join(bubbles).lower()


@pytest.mark.asyncio
async def test_d1_documents() -> None:
    result = await compose_followup(_plan_documents(), clock=GOLDEN_CLOCK_ISO)
    assert result.sendable
    assert 1 <= len(result.bubbles) <= 2
    joined = _joined(result.bubbles)
    assert any(token in joined for token in ("comprovante", "documento", "reunir"))
    assert "obrigat" not in joined
    assert "precisa enviar" not in joined
    assert "sou a júlia" not in joined
    assert result.composed_at == parse_clock(GOLDEN_CLOCK_ISO)


@pytest.mark.asyncio
async def test_d2_family_decision() -> None:
    result = await compose_followup(_plan_partner("Kwid 2023"))
    assert result.sendable
    joined = _joined(result.bubbles)
    assert "kwid 2023" in joined
    assert any(token in joined for token in ("conversar", "decidir", "família", "decisão"))
    assert len(result.bubbles) == 1


@pytest.mark.asyncio
async def test_d3_interrupted_simulation() -> None:
    result = await compose_followup(_plan_simulation("T-Cross 2019"))
    assert result.sendable
    joined = _joined(result.bubbles)
    assert "t-cross 2019" in joined
    assert any(token in joined for token in ("simula", "financi"))
    assert "aprovad" not in joined
    assert "taxa de" not in joined
    assert "parcela ficar" not in joined


@pytest.mark.asyncio
async def test_d4_specific_vehicle_label_from_authorized_facts() -> None:
    plan = FollowUpPlan(
        reason=FollowUpReason.SPECIFIC_VEHICLE.value,
        requested_action=FollowUpAction.ASK_VEHICLE_INTEREST.value,
        authorized_facts={"vehicle_label": "Renegade 2020"},
    )
    result = await compose_followup(
        plan,
        tool_results=_inventory(InventoryOutcome.SUCCESS_FOUND.value),
    )
    assert result.sendable
    assert "renegade 2020" in _joined(result.bubbles)


@pytest.mark.asyncio
async def test_d5_sold_vehicle_no_availability_no_substitute() -> None:
    plan = _plan_vehicle("Compass 2021")
    tools = _inventory(
        InventoryOutcome.SUCCESS_SOLD.value,
        alternatives=[{"title": "Corolla XEi", "model": "Corolla"}],
    )
    result = await compose_followup(plan, tool_results=tools)
    joined = _joined(result.bubbles)
    assert "disponível" not in joined
    assert "em estoque" not in joined
    assert "corolla" not in joined
    assert "alternativa" not in joined
    assert result.strategy == FollowUpStrategy.CANCEL_SAFE.value
    assert result.strategy_reason == "vehicle_sold"
    assert result.sendable

    reserved = await compose_followup(
        plan,
        tool_results=_inventory(
            InventoryOutcome.SUCCESS_FOUND.value,
            vehicles=[{"status": "RESERVED", "title": "Compass 2021"}],
            alternatives=[{"model": "Corolla"}],
        ),
    )
    assert reserved.strategy == FollowUpStrategy.CANCEL_SAFE.value
    assert reserved.strategy_reason == "vehicle_reserved"
    assert "corolla" not in _joined(reserved.bubbles)
    assert "disponível" not in _joined(reserved.bubbles)


@pytest.mark.asyncio
async def test_d6_unconfirmed_availability_does_not_assert_stock() -> None:
    result = await compose_followup(
        _plan_vehicle("Polo 2018"),
        tool_results=_inventory(InventoryOutcome.NOT_EXECUTED.value),
    )
    assert result.sendable
    joined = _joined(result.bubbles)
    assert "polo 2018" in joined
    assert "disponível" not in joined
    assert "em estoque" not in joined
    assert "ainda temos" not in joined


def test_d7_financial_promise_rejected() -> None:
    validation = validate_followup(
        ["A taxa será de 1,99% ao mês e o financiamento está aprovado."],
        _plan_simulation(),
    )
    assert not validation.sendable
    assert validation.bubbles == []
    assert "financial_promise" in validation.violations


def test_d8_undue_pressure_rejected() -> None:
    validation = validate_followup(
        ["Última chance, corre que vai acabar. Vi que você sumiu."],
        _plan_vehicle(),
    )
    assert not validation.sendable
    assert validation.bubbles == []
    assert "pressure" in validation.violations
    assert "absence_shame" in validation.violations


def test_d9_internal_leak_rejected() -> None:
    validation = validate_followup(
        ["Vou fazer o handoff no CRM e criar o lead na automação."],
        _plan_documents(),
    )
    assert not validation.sendable
    assert validation.bubbles == []
    assert "internal_leak" in validation.violations


@pytest.mark.asyncio
async def test_d10_repeated_question_and_no_reintro() -> None:
    result = await compose_followup(_plan_documents())
    assert result.sendable
    joined = _joined(result.bubbles)
    assert "sou a júlia" not in joined
    assert "como posso ajudar você hoje" not in joined
    assert not joined.startswith("oi")

    reintro = validate_followup(
        ["Oi! Sou a Júlia da FacilCar. Como posso ajudar você hoje?"],
        _plan_documents(),
    )
    assert not reintro.sendable
    assert "reintroduction" in reintro.violations

    last = result.bubbles[0]
    repeated = validate_followup(
        [last],
        FollowUpPlan(
            reason=FollowUpReason.DOCUMENTS_PENDING.value,
            requested_action=FollowUpAction.ASK_DOCUMENTS_STATUS.value,
            pending_commitment="send_proofs_later",
            authorized_facts={
                "pending_commitment": "send_proofs_later",
                "last_assistant_question": last,
            },
        ),
    )
    assert not repeated.sendable
    assert "repeated_question" in repeated.violations


@pytest.mark.asyncio
async def test_d11_contextual_fallback() -> None:
    class _BrokenClient:
        def __init__(self) -> None:
            self.chat = self
            self.completions = self

        async def create(self, **_kwargs: object) -> None:
            raise RuntimeError("llm unavailable")

    result = await compose_followup(
        _plan_partner("Versa 2022"),
        client=_BrokenClient(),
        clock=lambda: datetime(2026, 9, 7, 10, 0, tzinfo=TZ_BRT),
    )
    assert result.sendable
    assert result.used_fallback
    assert "versa 2022" in _joined(result.bubbles)
    assert result.composed_at is not None
    assert result.composed_at.hour == 10


def test_d12_empty_output_not_sendable() -> None:
    empty_plan = FollowUpPlan(
        reason=FollowUpReason.EMPTY.value,
        requested_action=FollowUpAction.DO_NOT_SEND.value,
    )
    empty_validation = validate_followup([], empty_plan)
    assert not empty_validation.sendable
    assert empty_validation.bubbles == []

    invalid = validate_followup(["   "], _plan_documents())
    assert not invalid.sendable
    assert "empty_output" in invalid.violations


@pytest.mark.asyncio
async def test_d12_empty_plan_compose_is_not_sendable() -> None:
    result = await compose_followup(
        FollowUpPlan(
            reason=FollowUpReason.EMPTY.value,
            requested_action=FollowUpAction.DO_NOT_SEND.value,
        )
    )
    assert not result.sendable
    assert result.bubbles == []
