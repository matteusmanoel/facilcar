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

    # Must never claim the FacilCar does not work with a vehicle category.
    if re.search(r"n[aã]o trabalhamos|n[aã]o temos esse tipo|nunca teremos", outbound_joined):
        fail(
            "GLOBAL: category_ban_as_stock",
            f"Response treated stock miss as category ban: {outbound_joined[:120]}",
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

    # Re-asking a field already collected is a contract failure.
    ask_field = plan.ask_field
    if ask_field and ask_field in (getattr(state, "collected_fields", None) or []):
        fail(
            "GLOBAL: repeat_answered_field",
            f"ask_field={ask_field!r} already in collected_fields={state.collected_fields}",
        )

    if "veículo publicado" in outbound_joined or "veiculo publicado" in outbound_joined:
        fail("GLOBAL: card_generic_title", "Outbound used generic 'Veículo publicado' title")

    if re.search(r"\bautomatic\b", outbound_joined) and "automático" not in outbound_joined:
        fail("GLOBAL: raw_enum_to_customer", f"Raw enum in outbound: {outbound_joined[:160]}")

    collected = getattr(state, "collected_fields", None) or []
    if not collected and re.search(r"j[áa]\s+reuni", outbound_joined):
        fail(
            "GLOBAL: false_completeness",
            "Claimed to have gathered information with empty collected_fields",
        )

    media = list(getattr(result, "outbound_media", None) or [])
    for item in media:
        caption = (getattr(item, "caption", None) or "").lower()
        if "veículo publicado" in caption or "veiculo publicado" in caption:
            fail("GLOBAL: card_must_identify_vehicle", caption[:160])
        if re.search(r"\bautomatic\b", caption):
            fail("GLOBAL: raw_enum_in_card", caption[:160])

    expected_facts_after = turn_def.get("expected_facts_after") or {}
    for fact_key, expected_val in expected_facts_after.items():
        actual_val = _fact_path(state.facts, fact_key)
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
        if not re.search(r"\d{1,2}\s*h", outbound_joined, re.I):
            fail(
                "invariant_two_concrete_slots",
                f"Slots must include exact hours, got: {outbound_joined[:180]}",
            )

    return violations


def _fact_path(facts: dict[str, Any], key: str) -> Any:
    if "." not in key:
        return facts.get(key)
    cur: Any = facts
    for part in key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def check_scenario(
    *,
    scenario: dict[str, Any],
    result: Any,
    llm_real: bool = False,
) -> list[InvariantViolation]:
    """End-of-conversation invariants. Empty list = pass."""
    violations: list[InvariantViolation] = []
    name = scenario.get("name", "unknown")

    def fail(invariant: str, detail: str = "") -> None:
        violations.append(InvariantViolation(name, -1, invariant, detail))

    expected_terminal = scenario.get("expected_terminal")
    obtained = _obtained_terminal(result)
    if expected_terminal and obtained != expected_terminal:
        fail(
            "SCENARIO: expected_terminal",
            f"expected {expected_terminal!r}, got {obtained!r}",
        )

    last_outbound = ""
    if result.turns:
        last = result.turns[-1]
        last_outbound = " ".join(last.get("outbound") or []).lower()
        last_action = (last.get("action") or "").upper()
        if expected_terminal == "HANDOFF_VENDOR" and last_action != "HANDOFF_VENDOR":
            if last.get("ask_field"):
                fail(
                    "SCENARIO: ended_on_question",
                    f"Conversation ended asking {last.get('ask_field')!r} instead of handoff",
                )

    state = getattr(result, "final_state", None)
    facts = getattr(state, "facts", {}) if state is not None else {}

    if name == "compra_avista":
        payment = str(facts.get("payment_method") or "").lower()
        if payment not in {"cash", "a_vista", "à vista"}:
            fail("SCENARIO: compra_avista_cash", f"payment_method={payment!r}")

    if name == "compra_financiada_com_entrada":
        if facts.get("down_payment") in (None, 0, "0"):
            fail("SCENARIO: down_payment_missing", f"down_payment={facts.get('down_payment')!r}")
        deferred = list(getattr(state, "deferred_fields", None) or []) if state else []
        if "documents" not in deferred and not facts.get("documents_deferred"):
            fail("SCENARIO: documents_not_deferred", f"deferred={deferred!r}")

    if name == "compra_financiada_sem_entrada":
        if facts.get("down_payment") not in (0, 0.0, "0"):
            fail("SCENARIO: zero_down", f"down_payment={facts.get('down_payment')!r}")

    if name in {"venda_direta", "consignacao", "refinanciamento"}:
        desired = facts.get("desired_vehicle") if isinstance(facts.get("desired_vehicle"), dict) else {}
        if desired.get("model") or facts.get("desired_model"):
            fail(
                "SCENARIO: customer_intent_no_desired",
                f"desired leaked into {name}: {desired or facts.get('desired_model')!r}",
            )

    if name.startswith("troca_"):
        from sdr.domain.vehicle_roles import customer_identity, desired_identity

        if state is not None and not desired_identity(facts):
            fail("SCENARIO: trade_desired_missing", str(facts.get("desired_vehicle")))
        if state is not None and not customer_identity(facts):
            fail("SCENARIO: trade_customer_missing", str(facts.get("customer_vehicle")))

    if name == "fox_peugeot_troca":
        if getattr(state, "last_inventory_outcome", None) == "SUCCESS_FOUND":
            shown = " ".join(str(x) for x in (getattr(state, "last_shown_vehicle_ids", None) or []))
            if "fox" in last_outbound and "argo" not in last_outbound:
                fail("SCENARIO: fox_treated_available", last_outbound[:160])

    if name == "pedido_de_vendedor":
        summary = (result.vendor_summary or "").lower()
        if "visita" in summary or "horário" in summary or "horario" in summary:
            fail("SCENARIO: vendor_summary_invented_visit", summary[:200])
        if "já reuni" in last_outbound:
            fail("SCENARIO: vendor_false_completeness", last_outbound[:160])

    if name.startswith("agendamento_"):
        if state is not None and not getattr(state, "visit_preferred_time", None):
            fail("SCENARIO: visit_slot_not_recorded", "visit_preferred_time is empty")
        if "esperamos você" in last_outbound and "vendedor" not in last_outbound:
            fail("SCENARIO: false_visit_confirmation", last_outbound[:160])

    if name == "civic_vendido_foto":
        sold_hits = [
            t for t in (result.turns or [])
            if t.get("matched_inventory_id") == "VH-SOLD-CIVIC-001"
            or t.get("inventory_outcome") == "SUCCESS_SOLD"
        ]
        if not sold_hits:
            match = getattr(state, "last_inventory_match", None) or {}
            fail("SCENARIO: sold_identity", f"no sold listing hit; last={match!r}")

    if name == "gol_nao_encontrado":
        # The Gol lookup itself must stay empty; later alternatives may find other cars.
        gol_outcomes = [
            t.get("inventory_outcome")
            for t in (result.turns or [])
            if t.get("inventory_query_model") and "gol" in str(t.get("inventory_query_model")).lower()
        ]
        if gol_outcomes and any(o != "SUCCESS_EMPTY" for o in gol_outcomes):
            fail("SCENARIO: gol_must_be_empty", str(gol_outcomes))

    if llm_real:
        if getattr(result, "fallback_count", 0):
            fail("SCENARIO: llm_fallback", f"fallbacks={result.fallback_count}")
        if any(not (t.get("outbound") or []) for t in (result.turns or []) if t.get("action") != "NO_REPLY"):
            fail("SCENARIO: empty_composer", "A turn produced no outbound text")

    return violations


def _obtained_terminal(result: Any) -> str:
    explicit = getattr(result, "obtained_terminal", None)
    if explicit:
        return str(explicit)
    turns = list(getattr(result, "turns", None) or [])
    if not turns:
        return "INCOMPLETE"
    last_action = (turns[-1].get("action") or "").upper()
    if last_action == "HANDOFF_VENDOR":
        return "HANDOFF_VENDOR"
    if last_action == "NO_REPLY":
        return "SILENCE"
    if turns[-1].get("ask_field"):
        return "INCOMPLETE"
    return last_action or "INCOMPLETE"
