"""Golden scenario invariants — assertions applied automatically on each replay turn."""

from __future__ import annotations

import re
from typing import Any

# Phrases the Composer must NEVER produce — financial/reservation promises.
_FORBIDDEN_PROMISE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"vou\s+reservar", re.I),
    re.compile(r"reservado\s+(?:para|pra)\s+você", re.I),
    re.compile(r"está\s+reservado", re.I),
    re.compile(r"deixar\s+reservado", re.I),
    re.compile(r"\bgarantido\b", re.I),
    re.compile(r"aprovação\s+garantida", re.I),
    re.compile(r"taxa\s+de\s+\d", re.I),
    re.compile(r"aprovado\s+no\s+crédito", re.I),
    re.compile(r"100%\s+financiado", re.I),
    re.compile(r"financ\w*\s+100", re.I),
]

# Phrases that indicate a "desired vehicle" question — forbidden for SALE/CONSIGNMENT/REFINANCING.
_DESIRED_VEHICLE_QUESTION_PHRASES = [
    "qual veículo você busca",
    "qual modelo você procura",
    "que carro você está procurando",
    "qual o carro que você quer",
    "qual modelo de carro você está buscando",
    "qual carro você está buscando",
]


class InvariantViolation(AssertionError):
    """Raised when a golden-scenario invariant fails."""

    def __init__(self, scenario: str, turn_idx: int, invariant: str, detail: str = ""):
        self.scenario = scenario
        self.turn_idx = turn_idx
        self.invariant = invariant
        self.detail = detail
        msg = f"[{scenario}] turn {turn_idx}: {invariant}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


def check_turn(
    *,
    scenario_name: str,
    turn_idx: int,
    turn_def: dict[str, Any],
    result: Any,  # ProcessTurnResult
) -> list[InvariantViolation]:
    """Validate a single turn against its spec. Returns list of violations (empty = pass)."""
    violations: list[InvariantViolation] = []

    def fail(invariant: str, detail: str = "") -> None:
        violations.append(InvariantViolation(scenario_name, turn_idx, invariant, detail))

    plan = result.action_plan
    outbound_texts: list[str] = list(result.outbound_texts or [])
    outbound_joined = " ".join(outbound_texts).lower()
    state = result.state

    # --- Global invariants (apply to every turn) ---

    # Must never say "não encontrei" as a permanent inventory absence
    if "não encontrei" in outbound_joined:
        fail(
            "GLOBAL: não_encontrei_banned",
            f"Response contains 'não encontrei': {outbound_joined[:120]}",
        )

    # Must never reopen as first contact after the assistant has already spoken.
    if turn_idx > 0:
        from sdr.domain.introduction import is_first_contact_reopen

        if is_first_contact_reopen(outbound_texts):
            fail(
                "GLOBAL: first_contact_reopen",
                f"Continuation turn reopened as first contact: {outbound_joined[:160]}",
            )

    # Forbidden financial/reservation promises — never allowed in any context.
    for pattern in _FORBIDDEN_PROMISE_PATTERNS:
        if pattern.search(outbound_joined):
            fail(
                "GLOBAL: forbidden_promise",
                f"Forbidden promise pattern {pattern.pattern!r} found in: {outbound_joined[:180]}",
            )

    # Intent-specific invariants.
    intent_val = getattr(state.intent, "value", str(state.intent)) if state else ""

    # SALE must not ask for desired vehicle.
    if intent_val == "sale":
        for phrase in _DESIRED_VEHICLE_QUESTION_PHRASES:
            if phrase in outbound_joined:
                fail(
                    "GLOBAL: SALE_no_desired_vehicle_question",
                    f"SALE intent asked for desired vehicle ({phrase!r}): {outbound_joined[:160]}",
                )

    # CONSIGNMENT must not use trade language.
    if intent_val == "consignment":
        if "carro que você quer trocar" in outbound_joined:
            fail(
                "GLOBAL: CONSIGNMENT_no_trade_language",
                f"CONSIGNMENT used trade language: {outbound_joined[:160]}",
            )

    # REFINANCING must not use trade language.
    if intent_val == "refinancing":
        if "carro que você quer trocar" in outbound_joined:
            fail(
                "GLOBAL: REFINANCING_no_trade_language",
                f"REFINANCING used trade language: {outbound_joined[:160]}",
            )

    # deal_type must not be asked when intent is already determined.
    if intent_val in ("trade", "sale", "consignment", "refinancing", "purchase", "purchase_financing"):
        if "seria compra ou troca" in outbound_joined or "seria uma compra ou troca" in outbound_joined:
            fail(
                "GLOBAL: NO_DEAL_TYPE_WHEN_INTENT_KNOWN",
                f"Asked 'compra ou troca' when intent is already {intent_val!r}: {outbound_joined[:160]}",
            )

    # --- Per-turn assertions ---

    expected_action = turn_def.get("expected_action")
    if expected_action:
        got = plan.action.value.upper() if hasattr(plan.action, "value") else str(plan.action).upper()
        if got != expected_action.upper():
            fail("expected_action", f"expected {expected_action!r}, got {got!r}")

    expected_outcome_in = turn_def.get("expected_outcome_in")
    if expected_outcome_in:
        inv_outcome = None
        for tr in result.tool_results or []:
            if tr.get("tool") == "inventory_search":
                inv_outcome = tr.get("outcome")
                break
        if inv_outcome not in expected_outcome_in:
            fail("expected_outcome_in", f"expected one of {expected_outcome_in!r}, got {inv_outcome!r}")

    expected_facts_after = turn_def.get("expected_facts_after") or {}
    for fact_key, expected_val in expected_facts_after.items():
        actual_val = state.facts.get(fact_key)
        if actual_val is None:
            fail(f"expected_facts_after[{fact_key}]", f"key missing; facts={dict(state.facts)}")
        elif expected_val is not None:
            # Normalize booleans: treat True/"true"/1 as equivalent, False/"false"/0 as equivalent
            def _normalize(v: Any) -> Any:
                if isinstance(v, bool):
                    return v
                if isinstance(v, str) and v.lower() in ("true", "false"):
                    return v.lower() == "true"
                return v

            norm_expected = _normalize(expected_val)
            norm_actual = _normalize(actual_val)
            if norm_expected != norm_actual:
                # For string comparison, do case-insensitive contains check
                if isinstance(norm_expected, str):
                    if norm_expected.lower() not in str(norm_actual).lower():
                        fail(f"expected_facts_after[{fact_key}]", f"expected {expected_val!r}, got {actual_val!r}")
                else:
                    fail(f"expected_facts_after[{fact_key}]", f"expected {expected_val!r}, got {actual_val!r}")

    forbidden_in_outbound = turn_def.get("forbidden_in_outbound") or []
    for forbidden in forbidden_in_outbound:
        if forbidden.lower() in outbound_joined:
            fail("forbidden_in_outbound", f"forbidden phrase {forbidden!r} found in: {outbound_joined[:120]}")

    expected_in_outbound_one_of = turn_def.get("expected_in_outbound_one_of") or []
    if expected_in_outbound_one_of:
        if not any(phrase.lower() in outbound_joined for phrase in expected_in_outbound_one_of):
            fail("expected_in_outbound_one_of", f"none of {expected_in_outbound_one_of!r} found in: {outbound_joined[:120]}")

    expected_ask_field_in = turn_def.get("expected_ask_field_in") or []
    if expected_ask_field_in:
        got_ask = plan.ask_field or ""
        if got_ask not in expected_ask_field_in:
            fail("expected_ask_field_in", f"expected one of {expected_ask_field_in!r}, got {got_ask!r}")

    # required_in_outbound_any — at least one phrase must appear in the outbound
    required_in_outbound_any = turn_def.get("required_in_outbound_any") or []
    if required_in_outbound_any:
        if not any(phrase.lower() in outbound_joined for phrase in required_in_outbound_any):
            fail("required_in_outbound_any", f"none of {required_in_outbound_any!r} found in: {outbound_joined[:180]}")

    # forbidden_action — action must NOT be this value
    forbidden_action = turn_def.get("forbidden_action")
    if forbidden_action:
        got = plan.action.value.upper() if hasattr(plan.action, "value") else str(plan.action).upper()
        if got == forbidden_action.upper():
            fail("forbidden_action", f"action {forbidden_action!r} was forbidden but got {got!r}")

    # invariant_two_concrete_slots — REGISTER_VISIT_INTEREST must offer ≥2 concrete time markers.
    if turn_def.get("invariant_two_concrete_slots"):
        time_markers = re.findall(
            r'\b(?:segunda|terça|quarta|quinta|sexta|sábado|domingo|'
            r'hoje|amanhã|\d{1,2}/\d{1,2})\b',
            outbound_joined,
            re.I,
        )
        if len(time_markers) < 2:
            fail(
                "invariant_two_concrete_slots",
                f"Expected ≥2 concrete time markers, found {time_markers!r} in: {outbound_joined[:180]}",
            )

    return violations
