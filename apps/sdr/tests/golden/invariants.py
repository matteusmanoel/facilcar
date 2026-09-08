"""Golden scenario invariants — assertions applied automatically on each replay turn."""

from __future__ import annotations

import re
from typing import Any

from sdr.domain.financial_promises import contains_forbidden_financial_promise

# Phrases the Composer must NEVER produce — financial/reservation promises.
# Isolated "taxa" is not a promise; numeric/guaranteed rates still are.
_FORBIDDEN_PROMISE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"vou\s+reservar", re.I),
    re.compile(r"reservado\s+(?:para|pra)\s+você", re.I),
    re.compile(r"está\s+reservado", re.I),
    re.compile(r"deixar\s+reservado", re.I),
    re.compile(r"\bgarantido\b", re.I),
    re.compile(r"aprovação\s+garantida", re.I),
    re.compile(r"taxa\s+de\s+\d", re.I),
    re.compile(r"taxa\s+será\s+(?:de\s+)?\d", re.I),
    re.compile(r"aprovado\s+no\s+crédito", re.I),
    re.compile(r"100%\s+financiado", re.I),
    re.compile(r"financ\w*\s+100\s*%\s+com\s+certeza", re.I),
    re.compile(r"financ\w*\s+100\s*%(?!\d)", re.I),
    re.compile(r"\bbanco\s+aprova\b", re.I),
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


INVARIANT_CATALOG: list[str] = [
    "GLOBAL: category_ban_as_stock",
    "GLOBAL: first_contact_reopen",
    "GLOBAL: forbidden_promise",
    "GLOBAL: SALE_no_desired_vehicle_question",
    "GLOBAL: CONSIGNMENT_no_trade_language",
    "GLOBAL: REFINANCING_no_trade_language",
    "GLOBAL: NO_DEAL_TYPE_WHEN_INTENT_KNOWN",
    "GLOBAL: repeat_answered_field",
    "GLOBAL: card_generic_title",
    "GLOBAL: raw_enum_to_customer",
    "GLOBAL: photos_promised_without_media",
    "GLOBAL: false_completeness",
    "GLOBAL: profile_complete_with_missing",
    "GLOBAL: profile_complete_with_deferred",
    "GLOBAL: collected_and_deferred",
    "GLOBAL: documents_collected_while_deferred",
    "GLOBAL: incompatible_desired_brand_model",
    "GLOBAL: debt_types_sem_multas",
    "GLOBAL: debt_clear_with_unknown",
    "GLOBAL: ambiguous_trade_question",
    "GLOBAL: success_found_without_offer",
    "GLOBAL: duplicate_vehicle_label",
    "GLOBAL: ask_field_question_mismatch",
    "GLOBAL: difference_financing_skips_installment",
    "GLOBAL: dialogue_alignment",
    "SCENARIO: cnh_deferred_not_granular",
    "SCENARIO: refinancing_false_complete",
    "SCENARIO: paid_off_described_as_financed",
    "SCENARIO: expectation_as_appraisal",
    "SCENARIO: duplicate_peugeot_label",
    "SCENARIO: honda_corolla",
    "SCENARIO: civic_color_leaked_to_corolla",
    "SCENARIO: documents_marked_collected",
    "SCENARIO: deferred_docs_ready_in_summary",
    "SCENARIO: cnh_deferred_marked_collected",
    "SCENARIO: sale_summary_invented_trade",
    "SCENARIO: sale_visit_marked",
    "SCENARIO: refinancing_false_no_pendency",
    "SCENARIO: summary_empty_claims",
    "SCENARIO: argo_without_identifiable_offer",
    "SCENARIO: ka_not_preserved",
    "SCENARIO: fines_cleared_all_debts",
    "SCENARIO: summary_validation",
    "SCENARIO: principal_event_not_executed",
    "SCENARIO: invariant_single_handoff",
    "SCENARIO: expected_primary_vehicle",
    "SCENARIO: expected_handoff_count",
    "SCENARIO: expected_crm_same_lead",
    "TURN: forbidden_action",
    "TURN: expected_outbound_empty",
    "TURN: expected_outbound_min",
    "TURN: expected_llm_calls",
    "TURN: expected_inbound_persisted",
    "TURN: inbound_persisted_on_silence",
    "TURN: expected_bot_status",
    "TURN: expected_suppressed_reason",
    "SCENARIO: expected_crm_status",
    "SCENARIO: expected_crm_monthly_payment",
    "SCENARIO: expected_crm_installments_not_money",
    "SCENARIO: expected_crm_reread",
    "SCENARIO: expected_summary_contains",
    "SCENARIO: location_sent_once",
    "SCENARIO: original_message_repeats_summary",
    "SCENARIO: empty_composer",
    "SCENARIO: admin_ownership_transition",
    "SCENARIO: suppressed_without_reason",
    "TURN: expected_inventory_search",
    "TURN: expected_runtime_calls",
    "TURN: expected_segment_count",
    "TURN: expected_primary_vehicle_id",
    "TURN: require_explicit_availability",
    "TURN: expected_docs_not_received",
    "SCENARIO: expected_followup_sends",
    "SCENARIO: expected_wait_state",
    "SCENARIO: expected_scheduled_at",
    "SCENARIO: followup_llm_when_cancelled",
    "SCENARIO: artifact_pii",
    "SCENARIO: one_followup_send",
    "TURN: expected_wait_state",
    "TURN: expected_followup_sends",
]


_EXPLICIT_AVAILABILITY = re.compile(
    r"\b(?:dispon[ií]vel|vendid[oa]|reservad[oa]|n[aã]o\s+confirmad[oa]|amb[ií]gu[oa]|"
    r"n[aã]o\s+est[aá]\s+mais|j[aá]\s+foi\s+vendid)\w*\b",
    re.I,
)
_GENERIC_STRADA_RAPPORT = re.compile(
    r"legal que gostou da strada(?!\s+20)",
    re.I,
)
_INTERNAL_LEAK = re.compile(
    r"\b(?:storage|bucket|s3|handoff|triagem|orchestrator|inboundturn)\b",
    re.I,
)
_QUESTIONNAIRE_CUES = (
    "envie tamb",
    "me envie",
    "pode enviar",
    "qual hor",
    "quando voc",
    "qual sua parcela",
    "qual o valor",
)

EVENT_KIND_CUSTOMER_INBOUND = "customer_inbound"
EVENT_KIND_ADMIN_EVENT = "admin_event"
EVENT_KIND_SUPPRESSED = "suppressed"
EVENT_KIND_CLOCK_JUMP = "clock_jump"
EVENT_KIND_SCHEDULER_TICK = "scheduler_tick"
EVENT_KIND_INVENTORY_OVERRIDE = "inventory_override"
EVENT_KIND_OPT_OUT = "opt_out"
_VALID_EVENT_KINDS = frozenset({
    EVENT_KIND_CUSTOMER_INBOUND,
    EVENT_KIND_ADMIN_EVENT,
    EVENT_KIND_SUPPRESSED,
    EVENT_KIND_CLOCK_JUMP,
    EVENT_KIND_SCHEDULER_TICK,
    EVENT_KIND_INVENTORY_OVERRIDE,
    EVENT_KIND_OPT_OUT,
})
_ADMIN_ACTIONS = frozenset({"ADMIN_ASSUME", "ADMIN_RESUME"})
_SUPPRESSED_REASONS = frozenset({"ai_silenced", "human_active", "human_or_handoff_silence"})
_ADMIN_STATUS = {"ADMIN_ASSUME": "HUMAN_ACTIVE", "ADMIN_RESUME": "AI_RESUMED"}


def classify_turn_event(turn: dict[str, Any] | None) -> dict[str, Any]:
    """Stamp/infer event_kind, composer_expected, outbound_expected.

    Admin events never call Composer. HUMAN_ACTIVE inbound is suppressed.
    Commercial NO_REPLY stays customer_inbound with outbound not expected.
    """
    turn = turn or {}
    action = str(turn.get("action") or "").upper()
    admin = turn.get("admin_event")
    suppressed_reason = str(turn.get("suppressed_reason") or "").strip()
    bot_status = str(turn.get("bot_status") or "")
    inbound = str(turn.get("inbound") or "").strip()

    if action in {"CLOCK_JUMP"} or turn.get("clock_jump") or turn.get("clock") and action == "CLOCK_JUMP":
        inferred = EVENT_KIND_CLOCK_JUMP
    elif action in {"SCHEDULER_TICK", "FOLLOWUP_SEND"} or turn.get("scheduler_tick"):
        inferred = EVENT_KIND_SCHEDULER_TICK
    elif action == "INVENTORY_OVERRIDE" or turn.get("inventory_override"):
        inferred = EVENT_KIND_INVENTORY_OVERRIDE
    elif action == "OPT_OUT" or turn.get("opt_out"):
        inferred = EVENT_KIND_OPT_OUT
    elif action in _ADMIN_ACTIONS or (isinstance(admin, (str, dict)) and admin):
        inferred = EVENT_KIND_ADMIN_EVENT
    elif suppressed_reason in _SUPPRESSED_REASONS or (
        action == "NO_REPLY" and bot_status == "HUMAN_ACTIVE"
    ):
        inferred = EVENT_KIND_SUPPRESSED
    else:
        inferred = EVENT_KIND_CUSTOMER_INBOUND

    kind = str(turn.get("event_kind") or "").strip() or inferred
    if kind not in _VALID_EVENT_KINDS:
        kind = inferred

    if "composer_expected" in turn:
        composer_expected = bool(turn.get("composer_expected"))
    elif kind in {
        EVENT_KIND_ADMIN_EVENT,
        EVENT_KIND_SUPPRESSED,
        EVENT_KIND_CLOCK_JUMP,
        EVENT_KIND_INVENTORY_OVERRIDE,
        EVENT_KIND_OPT_OUT,
    }:
        composer_expected = False
    elif kind == EVENT_KIND_SCHEDULER_TICK:
        composer_expected = bool(turn.get("outbound") or turn.get("expected_outbound_min"))
        if action == "FOLLOWUP_SEND":
            composer_expected = True
        if action == "SCHEDULER_TICK" and not (turn.get("outbound") or []):
            composer_expected = False
    else:
        composer_expected = action != "NO_REPLY"
        if not action and inbound:
            composer_expected = True

    if "outbound_expected" in turn:
        outbound_expected = bool(turn.get("outbound_expected"))
    else:
        outbound_expected = composer_expected

    return {
        "event_kind": kind,
        "composer_expected": composer_expected,
        "outbound_expected": outbound_expected,
    }


def _admin_ownership_transitioned(
    previous: dict[str, Any] | None,
    turn: dict[str, Any],
) -> bool:
    action = str(turn.get("action") or "").upper()
    expected_status = _ADMIN_STATUS.get(action)
    if not expected_status:
        admin = turn.get("admin_event")
        label = str(admin.get("type") if isinstance(admin, dict) else admin or "").lower()
        expected_status = "HUMAN_ACTIVE" if label == "assume" else "AI_RESUMED" if label == "resume" else None
    if not expected_status:
        return False
    status = str(turn.get("bot_status") or "")
    revision = int(turn.get("ownership_revision") or 0)
    previous_revision = int((previous or {}).get("ownership_revision") or 0)
    return status == expected_status and revision > previous_revision


def check_turn(
    *,
    scenario_name: str,
    turn_idx: int,
    turn_def: dict[str, Any],
    result: Any,  # ProcessTurnResult
    inbound: Any = None,
    runtime_calls: int = 1,
    llm_calls: int = 0,
    inbound_persisted: bool = False,
    suppressed_reason: str | None = None,
    followup: dict[str, Any] | None = None,
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
    # Canonical gate is assistant_turn_count, not JSON turn index: an isolated
    # ``/deletar`` is a protocol turn, and the next customer line is first contact.
    if getattr(state, "assistant_turn_count", 0) > 1:
        from sdr.domain.introduction import is_first_contact_reopen

        if is_first_contact_reopen(outbound_texts):
            fail(
                "GLOBAL: first_contact_reopen",
                f"Continuation turn reopened as first contact: {outbound_joined[:160]}",
            )

    # Forbidden financial/reservation promises — never allowed in any context.
    # Isolated "taxa" in a lender disclaimer is not a promise.
    if contains_forbidden_financial_promise(outbound_joined):
        fail(
            "GLOBAL: forbidden_promise",
            f"Forbidden financial promise found in: {outbound_joined[:180]}",
        )
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
    action_u = plan.action.value.upper() if hasattr(plan.action, "value") else str(plan.action).upper()
    if expected_action:
        got = action_u
        if got != expected_action.upper():
            fail("expected_action", f"expected {expected_action!r}, got {got!r}")

    forbidden_action = turn_def.get("forbidden_action")
    if forbidden_action and action_u == str(forbidden_action).upper():
        fail("TURN: forbidden_action", f"action {action_u} is forbidden")

    if turn_def.get("expected_outbound_empty") and outbound_texts:
        fail(
            "TURN: expected_outbound_empty",
            f"expected no outbound, got {outbound_texts!r}",
        )
    outbound_min = turn_def.get("expected_outbound_min")
    if outbound_min is not None and len(outbound_texts) < int(outbound_min):
        fail(
            "TURN: expected_outbound_min",
            f"expected at least {outbound_min} outbound bubble(s), got {len(outbound_texts)}",
        )
    expected_llm = turn_def.get("expected_llm_calls")
    if expected_llm is not None and int(llm_calls) != int(expected_llm):
        fail(
            "TURN: expected_llm_calls",
            f"expected {expected_llm} understand call(s), got {llm_calls}",
        )
    if turn_def.get("expected_inbound_persisted") and not inbound_persisted:
        fail("TURN: expected_inbound_persisted", "inbound was not persisted")
    reason_code = getattr(plan, "reason_code", None)
    silenced = action_u == "NO_REPLY" and str(reason_code or "") in {
        "ai_silenced",
        "human_or_handoff_silence",
        "human_active",
    }
    if silenced and (turn_def.get("inbound") or (inbound is not None)) and not inbound_persisted:
        fail(
            "TURN: inbound_persisted_on_silence",
            "HUMAN_ACTIVE inbound was dropped instead of persisted",
        )
    expected_bot = turn_def.get("expected_bot_status")
    if expected_bot:
        got_bot = getattr(getattr(state, "lifecycle", None), "status", None)
        got_bot_val = got_bot.value if hasattr(got_bot, "value") else str(got_bot or "")
        if got_bot_val != str(expected_bot):
            fail(
                "TURN: expected_bot_status",
                f"expected {expected_bot!r}, got {got_bot_val!r}",
            )
    expected_suppressed = turn_def.get("expected_suppressed_reason")
    if expected_suppressed and str(suppressed_reason or reason_code or "") != str(expected_suppressed):
        fail(
            "TURN: expected_suppressed_reason",
            f"expected {expected_suppressed!r}, got {suppressed_reason or reason_code!r}",
        )

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

    if re.search(r"envi(ar|o)\s+(umas\s+)?fotos|te enviar umas fotos", outbound_joined):
        media = list(getattr(result, "outbound_media", None) or [])
        if not media:
            fail(
                "GLOBAL: photos_promised_without_media",
                "Composer promised photos but no outbound media was produced",
            )

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

    # Completeness contract
    if state is not None:
        missing = list(getattr(state, "missing_fields", None) or [])
        deferred = list(getattr(state, "deferred_fields", None) or [])
        collected = list(getattr(state, "collected_fields", None) or [])
        if getattr(state, "profile_complete", False) and missing:
            fail("GLOBAL: profile_complete_with_missing", str(missing))
        if getattr(state, "profile_complete", False) and deferred:
            fail("GLOBAL: profile_complete_with_deferred", str(deferred))
        overlap = set(collected) & set(deferred)
        if overlap:
            fail("GLOBAL: collected_and_deferred", str(overlap))
        if "documents" in collected and (
            "documents" in deferred or "cnh" in deferred or state.facts.get("documents_deferred")
        ):
            fail("GLOBAL: documents_collected_while_deferred", f"collected={collected} deferred={deferred}")

        facts = state.facts or {}
        desired = facts.get("desired_vehicle") if isinstance(facts.get("desired_vehicle"), dict) else {}
        from sdr.domain.vehicle_catalog import brands_compatible

        if desired.get("brand") and desired.get("model"):
            if not brands_compatible(str(desired.get("brand")), str(desired.get("model"))):
                fail(
                    "GLOBAL: incompatible_desired_brand_model",
                    f"{desired.get('brand')} {desired.get('model')}",
                )
        cv = facts.get("customer_vehicle") if isinstance(facts.get("customer_vehicle"), dict) else {}
        if str(cv.get("debt_types") or "").lower() in {"sem_multas", "sem multa"}:
            fail("GLOBAL: debt_types_sem_multas", str(cv.get("debt_types")))
        checks = cv.get("debt_checks") if isinstance(cv.get("debt_checks"), dict) else {}
        if cv.get("debt_status") == "clear" and any(
            checks.get(k) == "unknown" for k in ("fines", "ipva", "licensing") if k in checks
        ):
            fail("GLOBAL: debt_clear_with_unknown", str(checks))

        ask = plan.ask_field
        if (
            getattr(state.intent, "value", "") == "trade"
            and desired.get("model")
            and cv.get("model")
            and ask in {"trade_year", "trade_color", "mileage", "trade_has_financing", "trade_has_debts"}
        ):
            customer_token = str(cv.get("model")).lower()
            if re.search(r"qual a cor do ve[ií]culo\?|qual o ano do ve[ií]culo\?", outbound_joined):
                if customer_token.split()[-1] not in outbound_joined and str(cv.get("brand") or "").lower() not in outbound_joined:
                    fail(
                        "GLOBAL: ambiguous_trade_question",
                        f"ask={ask} outbound={outbound_joined[:160]}",
                    )

    if (plan.action.value if hasattr(plan.action, "value") else str(plan.action)).upper() == "SHOW_OFFERS":
        inv_outcome = None
        vehicles = []
        for tr in result.tool_results or []:
            if tr.get("tool") == "inventory_search":
                inv_outcome = tr.get("outcome")
                vehicles = tr.get("vehicles") or []
                break
        if inv_outcome == "SUCCESS_FOUND":
            media = list(getattr(result, "outbound_media", None) or [])
            if not vehicles and not media:
                fail("GLOBAL: success_found_without_offer", "no vehicles and no media")
            if re.search(r"te enviar umas fotos", outbound_joined) and not media:
                fail("GLOBAL: promised_photos_without_media", outbound_joined[:160])

    if re.search(r"\b(\w+)\s+\1\b", outbound_joined) and re.search(
        r"peugeot 2008 2008|2008 2008", outbound_joined
    ):
        fail("GLOBAL: duplicate_vehicle_label", outbound_joined[:160])

    adherence = getattr(result, "question_adherence", None) or {}
    if (
        plan.ask_field
        and (plan.action.value if hasattr(plan.action, "value") else str(plan.action)).upper()
        in {"ASK_INFO", "SHOW_OFFERS"}
        and adherence
        and adherence.get("skipped") is False
        and adherence.get("match") is False
    ):
        fail(
            "GLOBAL: ask_field_question_mismatch",
            f"expected={adherence.get('expected_question_field')} "
            f"detected={adherence.get('detected_question_field')} "
            f"q={adherence.get('outbound_question')!r}",
        )

    facts = getattr(state, "facts", None) or {}
    if (
        str(facts.get("payment_applies_to") or "") == "difference"
        and str(facts.get("payment_method") or "") == "financing"
        and getattr(state, "intent", None) is not None
        and getattr(state.intent, "value", "") == "trade"
        and not facts.get("desired_installment")
        and plan.ask_field == "name"
        and "name" not in (getattr(state, "collected_fields", None) or [])
    ):
        fail(
            "GLOBAL: difference_financing_skips_installment",
            f"ask_field={plan.ask_field} missing installment after difference financing",
        )

    expected_runtime = turn_def.get("expected_runtime_calls")
    if expected_runtime is not None and int(expected_runtime) != int(runtime_calls):
        fail(
            "TURN: expected_runtime_calls",
            f"expected {expected_runtime} runtime call(s), got {runtime_calls}",
        )

    expected_segments = turn_def.get("expected_segment_count")
    if expected_segments is not None and inbound is not None:
        ref = getattr(inbound, "raw_message_ref", None) or {}
        got_seg = int(ref.get("segment_count") or len(getattr(inbound, "segments", None) or []) or 1)
        if got_seg != int(expected_segments):
            fail(
                "TURN: expected_segment_count",
                f"expected {expected_segments} inbound segments, got {got_seg}",
            )

    expected_search = turn_def.get("expected_inventory_search")
    if expected_search is not None:
        searched = any(
            (tr.get("tool") == "inventory_search") for tr in (result.tool_results or [])
        )
        if bool(expected_search) != searched:
            fail(
                "TURN: expected_inventory_search",
                f"expected inventory_search={expected_search!r}, got {searched}",
            )

    expected_primary = turn_def.get("expected_primary_vehicle_id")
    if expected_primary:
        got_primary = getattr(state, "primary_vehicle_id", None)
        if got_primary != expected_primary:
            fail(
                "TURN: expected_primary_vehicle_id",
                f"expected {expected_primary!r}, got {got_primary!r}",
            )
        shown = list(getattr(state, "last_shown_vehicle_ids", None) or [])
        extras_primary = [
            vid for vid in shown if vid != expected_primary and vid == got_primary
        ]
        _ = extras_primary

    if turn_def.get("require_explicit_availability"):
        if not _EXPLICIT_AVAILABILITY.search(outbound_joined):
            fail(
                "TURN: require_explicit_availability",
                f"no explicit availability stance in: {outbound_joined[:180]}",
            )

    not_received = turn_def.get("expected_docs_not_received") or []
    if not_received and state is not None:
        status = state.facts.get("document_status") if isinstance(state.facts.get("document_status"), dict) else {}
        for component in not_received:
            if status.get(component) == "received":
                fail(
                    "TURN: expected_docs_not_received",
                    f"{component} marked received after this turn: {status}",
                )

    if turn_def.get("storage_simulated") or (
        inbound is not None
        and isinstance(getattr(inbound, "raw_message_ref", None), dict)
        and inbound.raw_message_ref.get("storage_simulated")
    ):
        action_u = plan.action.value.upper() if hasattr(plan.action, "value") else str(plan.action).upper()
        if action_u in {"NO_REPLY", "MEDIA_FAILED"}:
            fail(
                "TURN: storage_failure_must_not_block",
                f"simulated Storage result blocked the conversation: action={action_u}",
            )
        if _INTERNAL_LEAK.search(outbound_joined):
            fail(
                "TURN: storage_failure_must_not_block",
                f"internal Storage leak in outbound: {outbound_joined[:160]}",
            )

    snap = followup or {}
    expected_wait = turn_def.get("expected_wait_state")
    if expected_wait and str(snap.get("wait_state") or "") != str(expected_wait):
        fail(
            "TURN: expected_wait_state",
            f"expected {expected_wait!r}, got {snap.get('wait_state')!r}",
        )
    expected_sends = turn_def.get("expected_followup_sends")
    if expected_sends is not None and int(snap.get("followup_sends") or 0) != int(expected_sends):
        fail(
            "TURN: expected_followup_sends",
            f"expected {expected_sends} send(s), got {snap.get('followup_sends')}",
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


def _principal_turn(turn_def: dict[str, Any]) -> bool:
    if turn_def.get("principal_event") or turn_def.get("expected_primary_vehicle_id"):
        return True
    if turn_def.get("clock_jump") or turn_def.get("scheduler_tick") or turn_def.get("inventory_override"):
        return True
    admin = turn_def.get("admin_event")
    if isinstance(admin, dict) and str(admin.get("type") or "").lower() in {
        "assume",
        "resume",
        "handoff",
    }:
        return True
    if str(turn_def.get("expected_action") or "").upper() == "HANDOFF_VENDOR":
        return True
    if turn_def.get("quoted_message_id") or turn_def.get("quoted"):
        return True
    events = turn_def.get("events")
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict) and (event.get("quoted_message_id") or event.get("quoted")):
                return True
    return False


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
    handoff_turns = [
        t
        for t in (result.turns or [])
        if str(t.get("action") or "").upper() == "HANDOFF_VENDOR"
    ]
    if expected_terminal == "HANDOFF_VENDOR":
        if not handoff_turns:
            fail(
                "SCENARIO: expected_terminal",
                f"expected {expected_terminal!r}, got {obtained!r}",
            )
    elif expected_terminal and obtained != expected_terminal:
        fail(
            "SCENARIO: expected_terminal",
            f"expected {expected_terminal!r}, got {obtained!r}",
        )

    last_outbound = ""
    if result.turns:
        last = result.turns[-1]
        last_outbound = " ".join(last.get("outbound") or []).lower()
        last_action = (last.get("action") or "").upper()
        if expected_terminal == "HANDOFF_VENDOR" and not handoff_turns:
            if last.get("ask_field"):
                fail(
                    "SCENARIO: ended_on_question",
                    f"Conversation ended asking {last.get('ask_field')!r} instead of handoff",
                )
            _ = last_action

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
        deferred = list(getattr(state, "deferred_fields", None) or []) if state else []
        status = facts.get("document_status") if isinstance(facts.get("document_status"), dict) else {}
        if "cnh" not in deferred and status.get("cnh") != "deferred":
            fail("SCENARIO: cnh_deferred_not_granular", f"deferred={deferred} status={status}")
        if "documents" in deferred and status.get("cnh") != "deferred":
            fail(
                "SCENARIO: cnh_deferred_not_granular",
                f"blob documents deferred without granular CNH: deferred={deferred} status={status}",
            )
        if getattr(state, "profile_complete", False):
            fail("SCENARIO: cnh_deferred_not_granular", "profile_complete true with deferred CNH")

    if name == "refinanciamento":
        if getattr(state, "profile_complete", False):
            fail(
                "SCENARIO: refinancing_false_complete",
                "MVP refinancing roteiro is handoff-minimum; profile_complete must stay false",
            )
        desired = facts.get("desired_vehicle") if isinstance(facts.get("desired_vehicle"), dict) else {}
        if desired.get("model") or facts.get("desired_model"):
            fail(
                "SCENARIO: customer_intent_no_desired",
                f"desired leaked into {name}: {desired or facts.get('desired_model')!r}",
            )

    if name in {"venda_direta", "consignacao"}:
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
        if "confirmação do vendedor" in last_outbound or "confirmacao do vendedor" in last_outbound:
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
        desired = facts.get("desired_vehicle") if isinstance(facts.get("desired_vehicle"), dict) else {}
        if str(desired.get("model") or "").lower() == "corolla" and str(desired.get("brand") or "").lower() == "honda":
            fail("SCENARIO: honda_corolla", str(desired))
        if str(desired.get("model") or "").lower() == "corolla" and str(desired.get("color") or "").lower() == "prata":
            fail("SCENARIO: civic_color_leaked_to_corolla", str(desired))
        summary = (result.vendor_summary or "").lower()
        if "honda" in summary and "corolla" in summary:
            fail("SCENARIO: summary_honda_corolla", result.vendor_summary or "")

    if name == "compra_financiada_com_entrada":
        deferred = list(getattr(state, "deferred_fields", None) or []) if state else []
        collected = list(getattr(state, "collected_fields", None) or []) if state else []
        if "documents" in collected:
            fail("SCENARIO: documents_marked_collected", str(collected))
        summary = (result.vendor_summary or "").lower()
        if re.search(r"documentos?.{0,40}prontos", summary):
            fail("SCENARIO: deferred_docs_ready_in_summary", result.vendor_summary or "")

    if name == "compra_financiada_sem_entrada":
        collected = list(getattr(state, "collected_fields", None) or []) if state else []
        if "documents" in collected:
            fail("SCENARIO: cnh_deferred_marked_collected", str(collected))

    if name == "venda_direta":
        summary = (result.vendor_summary or "").lower()
        if re.search(r"\btroca\b|\btrocar\b", summary):
            fail("SCENARIO: sale_summary_invented_trade", result.vendor_summary or "")
        if re.search(r"avalia[çc][aã]o da loja|\bavaliado em\b|\bvale\s+r\$", summary):
            fail("SCENARIO: expectation_as_appraisal", result.vendor_summary or "")
        if re.search(r"est[aá]\s+marcada|visita marcada|agendada", summary):
            fail("SCENARIO: sale_visit_marked", result.vendor_summary or "")
        if re.search(r"documentos?", summary):
            fail("SCENARIO: sale_inapplicable_documents", result.vendor_summary or "")

    if name == "refinanciamento":
        summary = (result.vendor_summary or "").lower()
        if re.search(r"sem pend[eê]ncias", summary):
            fail("SCENARIO: refinancing_false_no_pendency", result.vendor_summary or "")
        if re.search(r"\bvisita\b", summary):
            fail("SCENARIO: refinancing_invented_visit", result.vendor_summary or "")

    if name == "fox_peugeot_troca":
        blob = (result.vendor_summary or "") + " " + " ".join(
            " ".join(t.get("outbound") or []) for t in (result.turns or [])
        )
        if re.search(r"peugeot 2008 2008", blob, re.I):
            fail("SCENARIO: duplicate_peugeot_label", blob[:200])

    if name == "troca_com_debitos":
        cv = facts.get("customer_vehicle") if isinstance(facts.get("customer_vehicle"), dict) else {}
        summary = (result.vendor_summary or "").lower()
        if cv.get("financing_status") == "paid_off" and re.search(
            r"est[aá]\s+financiado", summary
        ) and "quitado" not in summary:
            fail("SCENARIO: paid_off_described_as_financed", result.vendor_summary or "")

    if name == "troca_financiada":
        if str(facts.get("payment_applies_to") or "") == "difference" and str(
            facts.get("payment_method") or ""
        ) == "financing":
            if facts.get("desired_installment") in (None, ""):
                fail("SCENARIO: difference_financing_no_installment", str(facts.get("payment_method")))
            if getattr(state, "profile_complete", False) and (
                getattr(state, "deferred_fields", None) or getattr(state, "missing_fields", None)
            ):
                fail("SCENARIO: incomplete_profile_marked_complete", str(state.missing_fields))

    if name == "fox_peugeot_troca":
        found_turns = [t for t in (result.turns or []) if t.get("inventory_outcome") == "SUCCESS_FOUND"]
        if found_turns:
            cards = found_turns[-1].get("vehicle_cards") or []
            titles = " ".join(str(c) for c in cards).lower()
            if "argo" not in titles and "argo" not in " ".join(found_turns[-1].get("outbound") or []).lower():
                fail("SCENARIO: argo_without_identifiable_offer", str(cards)[:200])

    if name == "troca_quitada":
        cv = facts.get("customer_vehicle") if isinstance(facts.get("customer_vehicle"), dict) else {}
        model = str(cv.get("model") or facts.get("trade_model") or "").lower()
        if "ka" not in model:
            fail("SCENARIO: ka_not_preserved", str(cv))

    if name == "troca_financiada":
        cv = facts.get("customer_vehicle") if isinstance(facts.get("customer_vehicle"), dict) else {}
        if cv.get("debt_status") == "clear" and "multas" in " ".join(
            str(t.get("inbound") or "") for t in (result.turns or [])
        ) and "ipva" not in str(cv.get("debt_checks") or {}).lower() and cv.get("debt_checks", {}).get("ipva") != "clear":
            # If conversation included IPVA confirmation, ipva must be clear; if only fines, must not be globally clear.
            only_fines = any("não tenho multas" in str(t.get("inbound") or "").lower() for t in (result.turns or []))
            ipva_said = any("ipva" in str(t.get("inbound") or "").lower() for t in (result.turns or []))
            if only_fines and not ipva_said and cv.get("debt_status") == "clear":
                fail("SCENARIO: fines_cleared_all_debts", str(cv))

    sv = getattr(result, "summary_validation", None)
    if sv and sv.get("pass") is False:
        fail("SCENARIO: summary_validation", str(sv.get("violations")))
    summary_text = result.vendor_summary or ""
    if summary_text and sv:
        from sdr.domain.summary_propositions import text_has_factual_assertions
        from sdr.domain.vendor_summary import CLAIM_POLICY_VENDOR_REQUEST

        policy = sv.get("claim_policy")
        if policy != CLAIM_POLICY_VENDOR_REQUEST:
            if text_has_factual_assertions(summary_text) and not (sv.get("claims") or []):
                fail("SCENARIO: summary_empty_claims", summary_text[:200])

    if name == "gol_nao_encontrado":
        # The Gol lookup itself must stay empty; later alternatives may find other cars.
        gol_outcomes = [
            t.get("inventory_outcome")
            for t in (result.turns or [])
            if t.get("inventory_query_model") and "gol" in str(t.get("inventory_query_model")).lower()
        ]
        if gol_outcomes and any(o != "SUCCESS_EMPTY" for o in gol_outcomes):
            fail("SCENARIO: gol_must_be_empty", str(gol_outcomes))

    executed_idxs = {t.get("idx") for t in (result.turns or [])}
    for idx, turn_def in enumerate(scenario.get("turns") or []):
        if not isinstance(turn_def, dict):
            continue
        if _principal_turn(turn_def) and idx not in executed_idxs:
            fail(
                "SCENARIO: principal_event_not_executed",
                f"turn {idx} never ran",
            )

    expected_primary = scenario.get("expected_primary_vehicle_id")
    if expected_primary and state is not None:
        if getattr(state, "primary_vehicle_id", None) != expected_primary:
            fail(
                "SCENARIO: expected_primary_vehicle",
                f"expected {expected_primary!r}, got {getattr(state, 'primary_vehicle_id', None)!r}",
            )

    expected_handoffs = scenario.get("expected_handoff_count")
    handoffs = sum(
        1
        for t in (result.turns or [])
        if str(t.get("action") or "").upper() == "HANDOFF_VENDOR"
    )
    notifications = int(getattr(result, "crm_handoff_count", 0) or 0)
    if handoffs > 1 or notifications > 1:
        fail(
            "SCENARIO: invariant_single_handoff",
            f"HANDOFF_VENDOR={handoffs} notifications={notifications}",
        )
    if expected_handoffs is not None and int(handoffs) != int(expected_handoffs):
        fail(
            "SCENARIO: expected_handoff_count",
            f"expected {expected_handoffs} handoff(s), got {handoffs}",
        )
    if expected_handoffs is not None and notifications and int(notifications) != int(expected_handoffs):
        fail(
            "SCENARIO: invariant_single_handoff",
            f"expected {expected_handoffs} notification(s), got {notifications}",
        )

    crm = getattr(result, "crm_report", None) or {}
    stored = crm.get("record_reread") or crm.get("payload_sent") or {}
    expected_crm_status = scenario.get("expected_crm_status")
    if expected_crm_status and stored.get("status") != expected_crm_status:
        fail(
            "SCENARIO: expected_crm_status",
            f"expected {expected_crm_status!r}, got {stored.get('status')!r}",
        )
    expected_monthly = scenario.get("expected_crm_monthly_payment")
    if expected_monthly is not None:
        fin = stored.get("financingRequest") or {}
        monthly = fin.get("desiredMonthlyPayment")
        try:
            monthly_n = float(monthly) if monthly is not None else None
        except (TypeError, ValueError):
            monthly_n = None
        if monthly_n != float(expected_monthly):
            fail(
                "SCENARIO: expected_crm_monthly_payment",
                f"desiredMonthlyPayment expected {expected_monthly!r}, got {monthly!r}",
            )
        prazo = fin.get("desiredInstallments")
        if prazo is not None:
            try:
                prazo_n = float(prazo)
            except (TypeError, ValueError):
                prazo_n = None
            if prazo_n == float(expected_monthly):
                fail(
                    "SCENARIO: expected_crm_installments_not_money",
                    f"desiredInstallments received monetary {prazo!r}",
                )
    if scenario.get("expected_crm_reread_matches") and crm and not crm.get("matches_payload"):
        fail("SCENARIO: expected_crm_reread", str(crm.get("matches_payload")))
    if scenario.get("expected_crm_same_lead"):
        lead_id = getattr(result, "crm_lead_id", None)
        stored_id = stored.get("id")
        if not lead_id or stored_id != lead_id:
            fail(
                "SCENARIO: expected_crm_same_lead",
                f"lead_id={lead_id!r} reread_id={stored_id!r}",
            )
    summary_needles = scenario.get("expected_summary_contains_any") or []
    if summary_needles:
        blob = (result.vendor_summary or "").lower()
        if not any(str(n).lower() in blob for n in summary_needles):
            fail(
                "SCENARIO: expected_summary_contains",
                f"none of {summary_needles!r} in summary: {(result.vendor_summary or '')[:180]}",
            )
    max_locations = scenario.get("expected_location_sends_max")
    if max_locations is not None:
        sends = int(getattr(result, "location_sends", 0) or 0)
        if getattr(state, "location_sent", False):
            sends = max(sends, 1)
        if sends > int(max_locations):
            fail("SCENARIO: location_sent_once", f"location sends={sends}")
    if stored.get("message") and stored.get("summary"):
        if str(stored.get("message") or "").strip() == str(stored.get("summary") or "").strip():
            fail(
                "SCENARIO: original_message_repeats_summary",
                "CRM message copied juliaSummary",
            )

    if llm_real:
        if getattr(result, "fallback_count", 0):
            fail("SCENARIO: llm_fallback", f"fallbacks={result.fallback_count}")

    turns = list(result.turns or [])
    for i, turn in enumerate(turns):
        semantics = classify_turn_event(turn)
        kind = semantics["event_kind"]
        idx = turn.get("idx", i)
        if kind == EVENT_KIND_ADMIN_EVENT:
            previous = turns[i - 1] if i else None
            if not _admin_ownership_transitioned(previous, turn):
                fail(
                    "SCENARIO: admin_ownership_transition",
                    f"turn {idx} action={turn.get('action')!r} "
                    f"bot_status={turn.get('bot_status')!r} "
                    f"revision={turn.get('ownership_revision')!r} "
                    f"previous_revision={(previous or {}).get('ownership_revision')!r}",
                )
            continue
        if kind in {
            EVENT_KIND_CLOCK_JUMP,
            EVENT_KIND_INVENTORY_OVERRIDE,
            EVENT_KIND_OPT_OUT,
        }:
            continue
        if kind == EVENT_KIND_SCHEDULER_TICK:
            if semantics["outbound_expected"] and not (turn.get("outbound") or []):
                fail(
                    "SCENARIO: empty_composer",
                    f"turn {idx} scheduler produced no outbound text",
                )
            continue
        if kind == EVENT_KIND_SUPPRESSED:
            reason = str(turn.get("suppressed_reason") or "").strip()
            if reason not in _SUPPRESSED_REASONS:
                fail(
                    "SCENARIO: suppressed_without_reason",
                    f"turn {idx} HUMAN_ACTIVE inbound lacks ai_silenced/human_active",
                )
            continue
        if semantics["outbound_expected"] and not (turn.get("outbound") or []):
            fail(
                "SCENARIO: empty_composer",
                f"turn {idx} produced no outbound text",
            )

    expected_sends = scenario.get("expected_followup_sends")
    got_sends = int(getattr(result, "followup_sends", 0) or 0)
    if expected_sends is not None and got_sends != int(expected_sends):
        fail(
            "SCENARIO: expected_followup_sends",
            f"expected {expected_sends} send(s), got {got_sends}",
        )
    if expected_sends == 1 and got_sends != 1:
        fail("SCENARIO: one_followup_send", f"sends={got_sends}")
    expected_wait = scenario.get("expected_wait_state")
    got_wait = str(getattr(result, "wait_state", None) or "")
    if expected_wait and got_wait != str(expected_wait):
        fail(
            "SCENARIO: expected_wait_state",
            f"expected {expected_wait!r}, got {got_wait!r}",
        )
    expected_sched = scenario.get("expected_scheduled_at")
    if expected_sched:
        tasks = list(getattr(result, "followup_tasks", None) or [])
        scheduled = [str(t.get("scheduledAt") or "") for t in tasks]
        if not any(expected_sched in item or item.startswith(str(expected_sched)[:19]) for item in scheduled):
            fail(
                "SCENARIO: expected_scheduled_at",
                f"expected {expected_sched!r} in {scheduled!r}",
            )
    if scenario.get("expected_no_llm_when_cancelled"):
        for turn in turns:
            action = str(turn.get("action") or "").upper()
            if action in {"ADMIN_ASSUME", "OPT_OUT"}:
                continue
            if str(turn.get("event_kind") or "") in {EVENT_KIND_ADMIN_EVENT, EVENT_KIND_OPT_OUT}:
                continue
            if action in {"SCHEDULER_TICK", "FOLLOWUP_SEND"} and int(turn.get("llm_calls") or 0) != 0:
                fail(
                    "SCENARIO: followup_llm_when_cancelled",
                    f"turn {turn.get('idx')} scheduler used LLM after cancel",
                )
            bot = str(turn.get("bot_status") or "")
            if bot == "HUMAN_ACTIVE" and int(turn.get("llm_calls") or 0) != 0 and turn.get("inbound"):
                fail(
                    "SCENARIO: followup_llm_when_cancelled",
                    f"turn {turn.get('idx')} LLM ran while HUMAN_ACTIVE",
                )
    if scenario.get("expected_artifact_clean"):
        from sdr.replay.followup_harness import pii_leaks, sanitize_artifact

        blob = str(sanitize_artifact({
            "turns": result.turns,
            "traces": getattr(result, "traces", None) or [],
            "tasks": getattr(result, "followup_tasks", None) or [],
        }))
        leaks = pii_leaks(blob)
        if leaks:
            fail("SCENARIO: artifact_pii", f"leaks={leaks[:5]!r}")

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


def collect_commercial_observations(
    *,
    scenario: dict[str, Any],
    result: Any,
    turn_def: dict[str, Any] | None = None,
    outbound_joined: str = "",
    action: str = "",
) -> list[dict[str, Any]]:
    """Mark known commercial behaviors without changing production or failing the freeze."""
    marks: list[dict[str, Any]] = []
    text = (outbound_joined or "").lower()
    if turn_def and turn_def.get("observe_availability") and text:
        if not _EXPLICIT_AVAILABILITY.search(text):
            marks.append(
                {
                    "code": "availability_implicit",
                    "severity": "commercial",
                    "detail": "Availability question was not answered with an explicit stance.",
                }
            )
    if _GENERIC_STRADA_RAPPORT.search(text):
        marks.append(
            {
                "code": "generic_vehicle_recognition",
                "severity": "commercial",
                "detail": "Primary vehicle referred to generically as Strada.",
            }
        )
    after_cnh = bool(turn_def and turn_def.get("observe_cnh_actions"))
    if after_cnh:
        actions = sum(1 for cue in _QUESTIONNAIRE_CUES if cue in text)
        bubbles = 0
        if result is not None:
            bubbles = len(getattr(result, "outbound_texts", None) or [])
        if bubbles >= 3 or actions >= 2:
            marks.append(
                {
                    "code": "cnh_multi_action",
                    "severity": "commercial",
                    "detail": f"bubbles={bubbles} questionnaire_cues={actions}",
                }
            )
    if re.search(r"como posso te ajudar hoje|em que posso te ajudar", text):
        marks.append(
            {
                "code": "artificial_rapport",
                "severity": "commercial",
                "detail": "Generic helper menu after intent was already known.",
            }
        )
    _ = scenario
    _ = action
    return marks
