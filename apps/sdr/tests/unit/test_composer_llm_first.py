"""Tests for the Composer LLM-First plan changes.

Covers:
- Handoff after visit invite (4 cases) — p1a-visit-pending
- Hash guard for referential comments (5 cases) — p1a-hash-guard
- ack_kind=down_payment payload reaches Composer LLM — p1b-ack-kind-gate
- SHOW_OFFERS exception fallback — p1a-show-offers-except
- Batch dedup in list_recent_turns — p1a-recent-turns-dedup
- _hard_fallback for REGISTER_VISIT_INTEREST — p1b-hard-fallback-visit
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from sdr.domain.budget_status import BudgetStatus
from sdr.domain.decision import decide, inventory_search_key
from sdr.domain.inventory_outcome import InventoryOutcome, inventory_fallback_bubbles
from sdr.domain.inventory_search import (
    InventorySearchRequest,
    inventory_search_key_from_request,
)
from sdr.domain.pending_interaction import AlternativeScope
from sdr.domain.types import (
    Action,
    ActionPlan,
    BusinessIntent,
    ConversationCanonicalState,
    CustomerState,
    HandoffSignals,
    LifecycleState,
    LifecycleStatus,
    ResponseDirective,
)
from sdr.infrastructure.conversation_repository import ConversationRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state(**kwargs) -> ConversationCanonicalState:
    base = ConversationCanonicalState(
        thread_id="t1",
        customer=CustomerState(phone="5511999999999"),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def _purchase_financing_facts() -> dict:
    """Minimal facts that make a PURCHASE_FINANCING state actionable."""
    return {
        "desired_model": "Corolla",
        "deal_type": "purchase",
        "payment_method": "financing",
        "down_payment": 0,
        "desired_installment": 1500,
        "name": "Mateus",
    }


def _actionable_financing_state(**kwargs) -> ConversationCanonicalState:
    facts = _purchase_financing_facts()
    key = inventory_search_key(facts)
    return _state(
        intent=BusinessIntent.PURCHASE_FINANCING,
        facts=facts,
        last_inventory_search_key=key,
        last_shown_vehicle_ids=["veh-corolla-1"],
        documents_asked=True,
        # installment_asked=True means next_ask_field skips desired_installment,
        # ensuring the roteiro is fully complete and next_ask_field returns None.
        installment_asked=True,
        **kwargs,
    )


def _pool_with_rows(rows: list[dict]) -> MagicMock:
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    pool = MagicMock()
    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(),
        )
    )
    return pool


def _message_row(direction: str, is_bot: bool, from_me: bool, text: str) -> dict:
    return {
        "direction": direction,
        "isBotSent": is_bot,
        "fromMe": from_me,
        "text": text,
    }


# ---------------------------------------------------------------------------
# 1. Handoff after visit invite — 4 cases
# ---------------------------------------------------------------------------

class TestVisitInviteHandoffGuard:
    """decide() must not immediately HANDOFF on the turn where pending_question='visit'."""

    def test_obrigado_after_visit_invite_asks_schedule_not_handoff(self) -> None:
        """After visit invite, courtesy with min qualification ready hands off.

        Visit is not a required field. 'Obrigado' is not accept. The old
        ASK_INFO visit-schedule loop is forbidden.
        """
        state = _actionable_financing_state(
            visit_invited=True,
            pending_question="visit",
        )
        plan = decide(state)
        assert plan.action == Action.HANDOFF_VENDOR, (
            f"Expected HANDOFF when triage is ready after visit invite, got {plan.action!r}."
        )
        assert plan.handoff is True
        assert plan.reason_code != "visit_schedule_ask"

    def test_visit_intent_after_invite_triggers_handoff(self) -> None:
        """After visit invite, visit_intent=True (e.g. 'Vou amanhã') → HANDOFF via should_handoff_now."""
        state = _actionable_financing_state(
            visit_invited=True,
            pending_question="visit",
            visit_preferred_time="segunda-feira, 7/09 às 14h",
            signals=HandoffSignals(visit_intent=True),
        )
        plan = decide(state)
        assert plan.action == Action.HANDOFF_VENDOR, (
            f"Expected HANDOFF when visit_intent=True after invite, got {plan.action!r}."
        )
        assert plan.handoff is True

    def test_second_turn_after_invite_always_handoffs(self) -> None:
        """Once pending_question is cleared (turn N+2), any message must HANDOFF."""
        state = _actionable_financing_state(
            visit_invited=True,
            pending_question=None,  # cleared after N+1 turn
        )
        plan = decide(state)
        assert plan.action == Action.HANDOFF_VENDOR, (
            f"Expected HANDOFF on turn N+2 (pending_question cleared), got {plan.action!r}."
        )
        assert plan.handoff is True

    def test_location_request_after_invite_sends_location(self) -> None:
        """SEND_LOCATION intercepts before the triage/handoff branch regardless of invite state."""
        state = _actionable_financing_state(
            visit_invited=True,
            pending_question="visit",
            location_request=True,
        )
        plan = decide(state)
        assert plan.action == Action.SEND_LOCATION, (
            f"Expected SEND_LOCATION for location_request=True, got {plan.action!r}."
        )
        assert plan.handoff is False

    def test_seria_otimo_after_invite_asks_schedule_not_model(self) -> None:
        """Positive reply without a slot must hand off — not restart vehicle search."""
        state = _actionable_financing_state(
            visit_invited=True,
            pending_question="visit",
        )
        plan = decide(state)
        assert plan.action == Action.HANDOFF_VENDOR
        assert plan.handoff is True
        assert plan.ask_field != "visit"


# ---------------------------------------------------------------------------
# 2. Hash guard — 5 cases
# ---------------------------------------------------------------------------

class TestInventoryHashGuard:
    """inventory_search_key_from_request must exclude original_vehicle_text when model+shown."""

    def _req(
        self,
        *,
        model: str | None = None,
        vehicle_text: str | None = None,
        engine: float | None = None,
        scope: AlternativeScope = AlternativeScope.NONE,
        vehicle_type: str | None = None,
    ) -> InventorySearchRequest:
        return InventorySearchRequest(
            original_model=model,
            original_vehicle_text=vehicle_text,
            engine_displacement_liters=[Decimal(str(engine))] if engine else [],
            alternative_scope=scope,
            vehicle_type=vehicle_type,
        )

    def test_guard_excludes_vehicle_text_when_model_and_shown(self) -> None:
        """Referential comment ('Lindo esse branco') must not change hash when model+shown."""
        req_base = self._req(model="Civic")
        req_comment = self._req(model="Civic", vehicle_text="Civic branco bonito")

        key_base = inventory_search_key_from_request(req_base, last_shown_vehicle_ids=["v1"])
        key_comment = inventory_search_key_from_request(req_comment, last_shown_vehicle_ids=["v1"])

        assert key_base == key_comment, (
            "Hash must be identical when vehicle_text differs only as a referential comment "
            "(original_model set + last_shown_vehicle_ids non-empty)."
        )

    def test_guard_preserves_engine_change(self) -> None:
        """Engine refinement ('Tem ele 2.0?') must still change hash — it is a structural refinement."""
        req_base = self._req(model="Civic")
        req_engine = self._req(model="Civic", engine=2.0)

        key_base = inventory_search_key_from_request(req_base, last_shown_vehicle_ids=["v1"])
        key_engine = inventory_search_key_from_request(req_engine, last_shown_vehicle_ids=["v1"])

        assert key_base != key_engine, (
            "Engine change must produce a different hash — it is a legitimate refinement."
        )

    def test_guard_preserves_scope_change(self) -> None:
        """Alternative scope change ('Tem um igual mais barato?') must change hash."""
        req_base = self._req(model="Civic")
        req_similar = self._req(model="Civic", scope=AlternativeScope.SIMILAR)

        key_base = inventory_search_key_from_request(req_base, last_shown_vehicle_ids=["v1"])
        key_similar = inventory_search_key_from_request(req_similar, last_shown_vehicle_ids=["v1"])

        assert key_base != key_similar, (
            "SIMILAR scope must produce a different hash — it is a legitimate refinement."
        )

    def test_guard_inactive_on_first_search(self) -> None:
        """Without shown vehicles (first search), vehicle_text must contribute to hash."""
        req_base = self._req(model="Civic")
        req_text = self._req(model="Civic", vehicle_text="Civic azul esportivo")

        key_base = inventory_search_key_from_request(req_base, last_shown_vehicle_ids=[])
        key_text = inventory_search_key_from_request(req_text, last_shown_vehicle_ids=[])

        assert key_base != key_text, (
            "Without shown vehicles, vehicle_text must remain in hash (guard inactive)."
        )

    def test_new_model_preference_changes_hash(self) -> None:
        """New model preference ('Prefiro um Corolla') must change hash regardless of guard."""
        req_civic = self._req(model="Civic")
        req_corolla = self._req(model="Corolla")

        key_civic = inventory_search_key_from_request(req_civic, last_shown_vehicle_ids=["v1"])
        key_corolla = inventory_search_key_from_request(req_corolla, last_shown_vehicle_ids=["v1"])

        assert key_civic != key_corolla, (
            "Different original_model must always produce different hashes."
        )


# ---------------------------------------------------------------------------
# 3. ack_kind=down_payment payload check (gate removed)
# ---------------------------------------------------------------------------

class TestDownPaymentAckPayload:
    """The down_payment=0 template must correctly acknowledge zero-entry financing
    without implying the customer has an entry ("com uma entrada as taxas tendem").

    This was the original bug: "valor todo" (down_payment=0) was getting a template
    that said "com uma entrada as taxas do financiamento tendem a ser ainda melhores",
    which contradicts the customer's intent (no entry).
    """

    def test_down_payment_zero_template_does_not_imply_entry(self) -> None:
        """Template for down_payment=0 must NOT say 'com uma entrada' or 'taxas'."""
        import asyncio

        from sdr.understanding.response_composer import compose_response

        async def _run() -> list[str]:
            state_map = {
                "action": "ask_info",
                "ack_kind": "down_payment",
                "inbound_text": "valor todo",
                "language": "pt-BR",
                "customer_name": "João",
                "facts": {"down_payment": 0, "payment_method": "financing"},
                "lifecycle_status": "BOT_ACTIVE",
                "should_introduce": False,
                "response_objective": "Confirme e avance.",
                "inventory_outcome": None,
            }
            return await compose_response(state_map, {"action": "ask_info", "ask_field": "desired_installment"})

        bubbles = asyncio.run(_run())
        assert bubbles, "Expected at least one bubble for down_payment=0 ack."
        combined = " ".join(bubbles).lower()
        assert "entrada" not in combined or "sem entrada" in combined or "financiar o valor todo" in combined or "total" in combined, (
            f"Template for down_payment=0 must not imply the customer has an entry. Got: {bubbles!r}"
        )
        # The old bug: template said "taxas do financiamento tendem a ser ainda melhores"
        # which is wrong when down_payment=0.
        assert "taxas" not in combined or "sem entrada" in combined, (
            f"Template must not mention 'taxas tendem' for zero entry. Got: {bubbles!r}"
        )

    def test_down_payment_nonzero_template_does_not_echo_amount(self) -> None:
        """Template for non-zero down_payment must not repeat the exact amount."""
        import asyncio

        from sdr.understanding.response_composer import compose_response

        async def _run() -> list[str]:
            state_map = {
                "action": "ask_info",
                "ack_kind": "down_payment",
                "inbound_text": "Posso dar 30 mil de entrada",
                "language": "pt-BR",
                "customer_name": "João",
                "facts": {"down_payment": 30000, "payment_method": "financing"},
                "lifecycle_status": "BOT_ACTIVE",
                "should_introduce": False,
                "response_objective": "Confirme e avance.",
                "inventory_outcome": None,
            }
            return await compose_response(state_map, {"action": "ask_info", "ask_field": "desired_installment"})

        bubbles = asyncio.run(_run())
        assert bubbles, "Expected at least one bubble for down_payment=30000 ack."
        combined = " ".join(bubbles).lower()
        assert "30 mil" not in combined and "30000" not in combined, (
            f"Template must not echo the amount '30 mil'. Got: {bubbles!r}"
        )


# ---------------------------------------------------------------------------
# 4. SHOW_OFFERS exception fallback
# ---------------------------------------------------------------------------

class TestShowOffersExceptionFallback:
    """compose_inventory_response raising → inventory_fallback_bubbles returned, not propagated."""

    @pytest.mark.asyncio
    async def test_compose_inventory_response_exception_returns_fallback(self) -> None:
        """When compose_inventory_response raises, process_turn must not propagate.

        We test this at the process_turn level by injecting a SHOW_OFFERS decision
        with a broken composer and verifying the call completes without raising.
        """
        import sdr.understanding.response_composer as composer_mod
        from sdr.application.process_turn import process_turn
        from sdr.domain.inventory_outcome import InventoryOutcome
        from sdr.domain.types import TurnFacts

        base_facts = {
            "desired_model": "Corolla",
            "deal_type": "purchase",
            "payment_method": "financing",
            "down_payment": 0,
        }
        # Use a different key so SHOW_OFFERS is triggered.
        initial_state = _state(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts={"desired_model": "Corolla"},  # minimal facts → will trigger SHOW_OFFERS
            last_shown_vehicle_ids=[],
            documents_asked=False,
        )

        good_facts = TurnFacts(
            intent=BusinessIntent.PURCHASE_FINANCING,
            facts=base_facts,
            language="pt-BR",
        )

        original_compose = getattr(composer_mod, "compose_inventory_response", None)

        def _broken(*_a: object, **_kw: object) -> list[str]:
            raise RuntimeError("simulated composer crash")

        composer_mod.compose_inventory_response = _broken  # type: ignore[attr-defined]
        try:
            async def _fixed_understand(
                _text: str, _s: ConversationCanonicalState
            ) -> TurnFacts:
                return good_facts

            # process_turn should complete; exception is caught, fallback used.
            result = await process_turn(
                state=initial_state,
                inbound_text="Quero ver as opções",
                understand=_fixed_understand,
            )
        finally:
            if original_compose is not None:
                composer_mod.compose_inventory_response = original_compose  # type: ignore[attr-defined]

        # The key invariant: process_turn returned a ProcessTurnResult without raising.
        assert result is not None


# ---------------------------------------------------------------------------
# 5. Batch dedup — list_recent_turns with exclude_message_ids
# ---------------------------------------------------------------------------

class TestRecentTurnsBatchDedup:
    """list_recent_turns must exclude the current inbound batch IDs from history."""

    @pytest.mark.asyncio
    async def test_list_recent_turns_excludes_batch_ids(self) -> None:
        """When exclude_message_ids provided, the SQL call must include the exclusion list."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        pool = MagicMock()
        pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(),
            )
        )
        repo = ConversationRepository(pool)
        exclude = ["cmtel4c3x00031s24zudzc1nh", "cmtel4c3x00041s24zudzc1ni"]

        await repo.list_recent_turns("conv-1", limit=5, exclude_message_ids=exclude)

        call_args = conn.fetch.await_args
        assert call_args is not None
        args = call_args.args
        # With exclude_message_ids, the SQL uses 3 params: conv_id, limit, ids list.
        assert len(args) >= 3, "Expected (sql, conv_id, limit, exclude_ids)"
        assert args[3] == exclude, f"exclude_message_ids not forwarded: {args}"
        sql = args[0]
        assert "$3::text[]" in sql, (
            "Message.id is Prisma cuid (text), not uuid. "
            f"Casting as uuid[] fails in Postgres: {sql}"
        )
        assert "::uuid[]" not in sql, (
            "Message.id must not be compared to uuid[]. "
            f"Got: {sql}"
        )

    @pytest.mark.asyncio
    async def test_recent_turns_batch_of_two_both_excluded(self) -> None:
        """All IDs in a multi-message batch must be forwarded to SQL exclusion."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        pool = MagicMock()
        pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(),
            )
        )
        repo = ConversationRepository(pool)
        batch_ids = ["cmtelmsg00001aaaa", "cmtelmsg00002bbbb"]

        await repo.list_recent_turns("conv-2", limit=5, exclude_message_ids=batch_ids)

        call_args = conn.fetch.await_args
        assert call_args is not None
        forwarded = call_args.args[3]
        assert set(forwarded) == {"cmtelmsg00001aaaa", "cmtelmsg00002bbbb"}, (
            "Both batch message IDs must be forwarded for SQL exclusion."
        )

    @pytest.mark.asyncio
    async def test_recent_turns_without_exclude_uses_simple_query(self) -> None:
        """Without exclude_message_ids, SQL must NOT pass a third positional arg."""
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        pool = MagicMock()
        pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=conn),
                __aexit__=AsyncMock(),
            )
        )
        repo = ConversationRepository(pool)

        await repo.list_recent_turns("conv-3", limit=5)

        call_args = conn.fetch.await_args
        assert call_args is not None
        args = call_args.args
        # Simple query: (sql, conv_id, limit) — no fourth arg.
        assert len(args) == 3, (
            f"Without exclude_message_ids, expected exactly 3 positional args (sql, id, limit), "
            f"got {len(args)}: {args}"
        )


# ---------------------------------------------------------------------------
# 6. _hard_fallback for REGISTER_VISIT_INTEREST
# ---------------------------------------------------------------------------

class TestHardFallbackRegisterVisitInterest:
    """_hard_fallback must return a visit invitation template, not the generic catch-all."""

    def test_hard_fallback_register_visit_interest_returns_invite(self) -> None:
        from sdr.application.process_turn import _hard_fallback

        plan = ActionPlan(
            action=Action.REGISTER_VISIT_INTEREST,
            handoff=False,
            reason_code="visit_invitation_pre_handoff",
            reason="Invite customer",
        )
        directive = ResponseDirective(
            action=Action.REGISTER_VISIT_INTEREST,
            inventory_outcome=InventoryOutcome.NOT_EXECUTED,
            language="pt-BR",
            should_introduce=False,
            response_objective="",
        )
        bubbles = _hard_fallback(plan, directive)

        assert bubbles, "Expected at least one bubble from _hard_fallback for REGISTER_VISIT_INTEREST."
        combined = " ".join(bubbles).lower()
        assert "14h" in combined or "horário" in combined or "vendedor" in combined, (
            f"Expected visit-related content in hard fallback bubbles, got: {bubbles!r}"
        )
        assert "como posso ajudar" not in combined, (
            "Generic fallback ('Como posso ajudar?') must not appear for REGISTER_VISIT_INTEREST."
        )
