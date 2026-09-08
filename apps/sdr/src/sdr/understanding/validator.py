"""Response validation — promise language + inventory truth + affordance policy."""

from __future__ import annotations

import logging
import re
from typing import Any

from sdr.domain.inventory_outcome import (
    contains_absence_claim,
    contains_policy_claim,
    inventory_fallback_bubbles,
)
from sdr.domain.dialogue_plan import (
    DialogueAct,
    DialoguePlan,
    DirectQuestionKind,
    contains_financing_approval_claim,
    contains_internal_leak,
    contains_vendor_confirmation,
    fallback_bubbles,
    infer_realized_acts,
    looks_like_intent_menu,
    question_count,
    reciprocity_present,
)
from sdr.domain.introduction import (
    continuation_smalltalk_bubbles,
    is_first_contact_reopen,
    strip_greeting_opener,
)
from sdr.domain.pending_interaction import PendingInteraction
from sdr.domain.types import InventoryOutcome

logger = logging.getLogger(__name__)

_PROMISE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(?:taxa|interes[eé]s?)\s*(?:de\s*)?\d+(?:[.,]\d+)?\s*%",
            re.I,
        ),
        "as condições de taxa dependem da análise da financeira",
    ),
    (
        re.compile(r"\b\d+(?:[.,]\d+)?\s*%\s*(?:ao\s*m[eê]s|a\.?m\.?|am)\b", re.I),
        "as condições de taxa dependem da análise da financeira",
    ),
    (
        re.compile(
            r"\b(?:aprovado|aprovada|garanti(?:do|da)|aprova(?:mos|ção)\s+garantida)\b",
            re.I,
        ),
        "sujeito à análise de crédito",
    ),
    (
        re.compile(r"\b100\s*%\s*financiado\b", re.I),
        "financiamento sem entrada pode ser possível, sujeito à análise",
    ),
    (
        re.compile(
            r"\bvamos\s+financiar\s+(?:o\s+valor\s+)?(?:todo|tudo)\b|"
            r"\bfinanciaremos\s+el\s+valor\s+total\b|"
            r"\bfinanciar\s+o\s+valor\s+todo\b",
            re.I,
        ),
        "podemos fazer uma simulação sem entrada, sujeito à análise da financeira",
    ),
    (
        re.compile(r"\btaxa\s+garantida\b", re.I),
        "as condições de taxa dependem da análise da financeira",
    ),
    (
        re.compile(r"\bfinanciamento\s+aprovado\b", re.I),
        "sujeito à análise de crédito",
    ),
    (
        re.compile(
            r"\b(?:fica|ser[aá]|sai|aprovad\w*|garanti\w*)\s+.{0,24}parcela\s*(?:de\s*)?R\$\s*[\d.]+(?:,\d+)?",
            re.I,
        ),
        "o valor da parcela depende da análise da financeira",
    ),
]

# CTAs that require a matching conversational_affordance / Decision continuation.
_UNAUTHORIZED_AFFORDANCE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"quer\s+que\s+eu\s+(?:veja|te\s+mostre|mostre)\s+alternativ",
            re.I,
        ),
        "offer_alternatives_without_affordance",
    ),
    (
        re.compile(
            r"\b(?:posso\s+te\s+avisar|te\s+aviso)\s+quando\s+(?:chegar|tiver)\b",
            re.I,
        ),
        "notify_when_available_without_affordance",
    ),
    (
        re.compile(r"\bquer\s+agendar\b", re.I),
        "schedule_without_affordance",
    ),
]

_RIGID_ORIGINAL_MODEL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"que\s+legal\s+que\s+voc[eê]\s+quer\s+(?:um|uma)\s+\w+", re.I),
    re.compile(r"or[cç]amento\s+que\s+voc[eê]\s+est[aá]\s+pensando\s+para\s+o\s+\w+", re.I),
]


_BUDGET_ASK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bor[cç]amento\b", re.I),
    re.compile(r"valor m[aá]ximo\s+voc[eê]\s+pensa\s+em\s+investir", re.I),
    re.compile(r"qual(?:\s+é)?\s+o\s+seu\s+or[cç]amento", re.I),
    re.compile(r"quanto\s+voc[eê]\s+(?:quer|pensa|pode)\s+investir", re.I),
    re.compile(r"or[cç]amento\s+para\s+o\s+", re.I),
]

# Questions the Decision Engine never plans — Composer must not invent them.
_OFF_ROTEIRO_ASK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bcons[oó]rcio\b", re.I),
    re.compile(r"uso\s+pessoal\s+ou\s+(?:para\s+)?empresa", re.I),
    re.compile(r"para\s+uso\s+pessoal\s+ou", re.I),
    re.compile(r"prazo\s+mais\s+curto", re.I),
    re.compile(r"parcelas\s+menores", re.I),
    re.compile(r"quantos\s+meses", re.I),
    re.compile(r"em\s+quantas\s+parcelas", re.I),
]

_CHEERLEADING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"que\s+[oó]timo\s+saber\s+que\s+vai\s+ser\s+compra", re.I),
    re.compile(r"condi[cç][oõ]es\s+tendem\s+a\s+ser\s+(?:melhores|mais\s+acess[ií]veis)", re.I),
]

_PAYMENT_BOTH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r",?\s*ou os dois\??", re.I),
    re.compile(r",?\s*o los dos\??", re.I),
]

_ROBOTIC_ACK_LINE = re.compile(
    r"^\s*(?:anotei\b.*|anoté\b.*|"
    r"beleza,\s*então é compra\.?|"
    r"perfecto,\s*entonces es (?:compra|permuta)\.?)\s*$",
    re.I,
)
_DEAL_TYPE_FALLBACK_PT = "Seria compra ou troca?"
_DEAL_TYPE_FALLBACK_ES = "¿Sería compra o permuta?"


def validate_bubbles(bubbles: list[str], *, language: str = "pt-BR") -> list[str]:
    """Return bubbles with prohibited promise/budget-ask phrasing rewritten."""
    cleaned: list[str] = []
    deal_fallback = (
        _DEAL_TYPE_FALLBACK_ES if str(language).lower().startswith("es") else _DEAL_TYPE_FALLBACK_PT
    )
    for bubble in bubbles:
        if not isinstance(bubble, str):
            continue
        text = bubble.strip()
        if not text:
            continue
        original = text
        if _ROBOTIC_ACK_LINE.match(text):
            continue
        for pattern, replacement in _PROMISE_PATTERNS:
            if pattern.search(text):
                text = pattern.sub(replacement, text)
        for pattern in _PAYMENT_BOTH_PATTERNS:
            text = pattern.sub("", text).rstrip(" ,")
        if not text:
            continue
        if any(pattern.search(text) for pattern in _BUDGET_ASK_PATTERNS):
            logger.warning("validate_bubbles: stripped budget solicitation: %r", original)
            text = deal_fallback
        if any(pattern.search(text) for pattern in _OFF_ROTEIRO_ASK_PATTERNS):
            logger.warning("validate_bubbles: stripped off-roteiro question: %r", original)
            continue
        if any(pattern.search(text) for pattern in _CHEERLEADING_PATTERNS):
            logger.warning("validate_bubbles: stripped cheerleading: %r", original)
            continue
        if text != original and text != deal_fallback:
            logger.warning(
                "validate_bubbles: softened promise language: %r -> %r",
                original,
                text,
            )
        cleaned.append(text)
    return cleaned[:3]


def _parse_affordance(raw: Any) -> PendingInteraction:
    if isinstance(raw, PendingInteraction):
        return raw
    try:
        return PendingInteraction(str(raw or "NONE"))
    except ValueError:
        return PendingInteraction.NONE


def validate_inventory_policy(
    bubbles: list[str],
    *,
    inventory_outcome: InventoryOutcome | str | None,
    language: str = "pt-BR",
    conversational_affordance: PendingInteraction | str | None = None,
    alternative_scope: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Enforce inventory truth + conversational affordance on composed bubbles.

    Returns ``(bubbles_or_fallback, validation_result)``.
    On policy violation, replaces with deterministic safe fallback.
    """
    if inventory_outcome is None:
        outcome = InventoryOutcome.NOT_EXECUTED
    elif isinstance(inventory_outcome, InventoryOutcome):
        outcome = inventory_outcome
    else:
        try:
            outcome = InventoryOutcome(str(inventory_outcome))
        except ValueError:
            outcome = InventoryOutcome.NOT_EXECUTED

    affordance = _parse_affordance(conversational_affordance)
    joined = " ".join(b for b in bubbles if isinstance(b, str))
    result: dict[str, Any] = {
        "outcome": outcome.value,
        "pass": True,
        "violations": [],
        "affordance": affordance.value,
    }

    if outcome in (
        InventoryOutcome.FAILED_RETRYABLE,
        InventoryOutcome.FAILED_TERMINAL,
        InventoryOutcome.NOT_EXECUTED,
    ):
        if contains_absence_claim(joined):
            result["pass"] = False
            result["violations"].append("absence_claim_on_failure")
        if contains_policy_claim(joined):
            result["pass"] = False
            result["violations"].append("policy_claim_on_failure")

    if outcome == InventoryOutcome.SUCCESS_EMPTY:
        if contains_policy_claim(joined):
            result["pass"] = False
            result["violations"].append("permanent_policy_claim_on_empty")

    # Composer must not invent CTAs the Decision Engine cannot consume.
    if affordance != PendingInteraction.OFFER_ALTERNATIVES:
        for pattern, code in _UNAUTHORIZED_AFFORDANCE_PATTERNS:
            if pattern.search(joined):
                # alternatives CTA specifically
                if code == "offer_alternatives_without_affordance":
                    result["pass"] = False
                    result["violations"].append(code)
                elif code in (
                    "notify_when_available_without_affordance",
                    "schedule_without_affordance",
                ):
                    result["pass"] = False
                    result["violations"].append(code)

    scope = (alternative_scope or "").upper()
    if scope in {"ANY_VEHICLE", "SIMILAR"}:
        for pattern in _RIGID_ORIGINAL_MODEL_PATTERNS:
            if pattern.search(joined):
                result["pass"] = False
                result["violations"].append("rigid_original_model_after_scope_widen")
                break

    if not result["pass"]:
        logger.warning(
            "validate_inventory_policy: rejected bubbles for outcome=%s violations=%s text=%r",
            outcome.value,
            result["violations"],
            joined[:200],
        )
        # Affordance-aware empty fallback: only ask alternatives when authorized.
        if (
            outcome == InventoryOutcome.SUCCESS_EMPTY
            and affordance == PendingInteraction.OFFER_ALTERNATIVES
        ):
            fallback = inventory_fallback_bubbles(outcome, language=language)
        elif outcome == InventoryOutcome.SUCCESS_EMPTY:
            es = language.lower().startswith("es")
            fallback = [
                "No encontré una opción con ese perfil en el stock actual."
                if es
                else "Não encontrei uma opção com esse perfil no estoque atual."
            ]
        else:
            fallback = inventory_fallback_bubbles(outcome, language=language)
        result["fallback_used"] = True
        return fallback, result

    result["fallback_used"] = False
    return validate_bubbles(bubbles, language=language), result


def validate_introduction_policy(
    bubbles: list[str],
    *,
    should_introduce: bool,
    action: str = "",
    language: str = "pt-BR",
) -> tuple[list[str], dict[str, Any]]:
    """Reject first-contact reopenings when the assistant has already spoken.

    Continuation turns must not open as a new greeting. This is protocol
    (conversation phase), not a product-term heuristic.
    """
    result: dict[str, Any] = {
        "pass": True,
        "violations": [],
        "fallback_used": False,
    }
    if should_introduce or not is_first_contact_reopen(bubbles):
        return bubbles, result

    result["pass"] = False
    result["violations"].append("first_contact_reopen")
    result["fallback_used"] = True
    logger.warning(
        "validate_introduction_policy: first-contact reopen action=%s text=%r",
        action,
        " ".join(bubbles)[:200],
    )
    if action == "smalltalk":
        return continuation_smalltalk_bubbles(language), result

    stripped: list[str] = []
    for i, bubble in enumerate(bubbles):
        text = bubble.strip() if isinstance(bubble, str) else ""
        if not text:
            continue
        if i == 0:
            text = strip_greeting_opener(text)
        if text and not is_first_contact_reopen([text]):
            stripped.append(text)
    if stripped:
        return stripped, result
    return continuation_smalltalk_bubbles(language), result


_REASK_PATTERNS: dict[str, re.Pattern[str]] = {
    "down_payment": re.compile(
        r"\b(?:tem\s+ideia\s+de\s+entrada|valor\s+de\s+entrada|quanto\s+de\s+entrada|"
        r"como\s+voc[eê]\s+pensa\s+nessa\s+negocia[cç][aã]o)\b",
        re.I,
    ),
    "desired_installment": re.compile(r"at[eé]\s+quanto\s+de\s+parcela", re.I),
    "payment_method": re.compile(r"[aà]\s+vista\s+ou\s+financiado", re.I),
}

_INVENTED_FEATURE = re.compile(
    r"sim,?\s+tem\s+teto\s+solar|de\s+s[eé]rie\s+e\s+teto|pano?r[aâ]mico\s+de\s+s[eé]rie",
    re.I,
)


def validate_dialogue_plan(
    bubbles: list[str],
    plan: DialoguePlan | dict | None,
    *,
    language: str = "pt-BR",
    customer_name: str | None = None,
    next_question: str | None = None,
    document_kind: str | None = None,
    should_introduce: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    """Enforce semantic obligations without matching a fixed copy."""
    parsed = DialoguePlan.from_mapping(plan) if not isinstance(plan, DialoguePlan) else plan
    result: dict[str, Any] = {
        "pass": True,
        "violations": [],
        "fallback_used": False,
        "requested_acts": list(parsed.acts),
        "realized_acts": [],
        "canonical_question": parsed.canonical_question,
        "facts_acknowledged": list(parsed.facts_to_acknowledge),
        "restrictions": list(parsed.restrictions),
    }
    cleaned = [b.strip() for b in bubbles if isinstance(b, str) and b.strip()]
    joined = " ".join(cleaned)

    def _fail(code: str) -> None:
        result["pass"] = False
        if code not in result["violations"]:
            result["violations"].append(code)

    if parsed.wellbeing_reciprocity and not reciprocity_present(joined):
        _fail("ignored_direct_question")
    if parsed.skip_generic_intent_menu and looks_like_intent_menu(joined):
        _fail("generic_menu_when_intent_known")
    if parsed.skip_reintroduce and is_first_contact_reopen(cleaned):
        _fail("unnecessary_reintroduction")
    if contains_internal_leak(joined):
        _fail("internal_process_leak")
    if contains_vendor_confirmation(joined):
        _fail("visit_vendor_confirmation")
    if contains_financing_approval_claim(joined):
        _fail("financing_as_approved")
    if DialogueAct.SAFETY_DISCLAIMER.value in parsed.acts:
        if not re.search(r"an[aá]lise|financeira|simula", joined, re.I):
            kinds = {str(q.get("kind")) for q in parsed.direct_questions}
            if DirectQuestionKind.FINANCING_100.value in kinds:
                _fail("ignored_direct_question")
                _fail("missing_safety_disclaimer")

    kinds = {str(q.get("kind")) for q in parsed.direct_questions}
    if DirectQuestionKind.UNKNOWN.value in kinds:
        unknown_q = next(
            (q for q in parsed.direct_questions if q.get("kind") == DirectQuestionKind.UNKNOWN.value),
            None,
        )
        if unknown_q and not unknown_q.get("answerable", True):
            if _INVENTED_FEATURE.search(joined) and not re.search(
                r"n[aã]o\s+tenho|n[aã]o\s+consigo\s+confirmar|equipe", joined, re.I
            ):
                _fail("invented_information")

    if DirectQuestionKind.FINANCING_100.value in kinds:
        if not re.search(r"sem\s+entrada|simula|an[aá]lise|financeira", joined, re.I):
            _fail("ignored_direct_question")
        if _REASK_PATTERNS["down_payment"].search(joined):
            _fail("repeated_answered_question")

    if DirectQuestionKind.ACCEPT_TRADE.value in kinds:
        if not re.search(r"troca|permuta", joined, re.I):
            _fail("ignored_direct_question")

    if DirectQuestionKind.AVAILABILITY.value in kinds:
        status = parsed.availability_status or ""
        if status == "available" and not re.search(r"dispon[ií]vel", joined, re.I):
            _fail("ignored_direct_question")
        elif status == "sold" and not re.search(r"vendid", joined, re.I):
            _fail("ignored_direct_question")
        elif status == "reserved" and not re.search(r"reserv", joined, re.I):
            _fail("ignored_direct_question")
        elif status == "ambiguous" and not re.search(
            r"mais de uma|v[aá]rias|qual dessas", joined, re.I
        ):
            _fail("ignored_direct_question")
        elif status in {"unresolved", "unknown", "unpublished", ""}:
            if not re.search(
                r"dispon[ií]vel|vendid|reserv|n[aã]o consegui confirmar|mais de uma|"
                r"n[aã]o est[aá] dispon",
                joined,
                re.I,
            ):
                _fail("ignored_direct_question")

    for field_name in parsed.forbid_reask_fields:
        pattern = _REASK_PATTERNS.get(field_name)
        if pattern and pattern.search(joined):
            _fail("repeated_answered_question")

    if parsed.max_questions == 1 and question_count(cleaned) > 2:
        _fail("incompatible_canonical_questions")
    if parsed.courtesy_only and question_count(cleaned) > 0 and re.search(
        r"parcela|entrada|comprar|trocar|cnh", joined, re.I
    ):
        _fail("repeated_answered_question")

    label = (parsed.proven_vehicle_label or "").lower()
    if label and "strada" in label and re.search(r"\bcivic\b", joined, re.I):
        _fail("wrong_vehicle")

    result["realized_acts"] = infer_realized_acts(cleaned, parsed)

    if result["pass"]:
        return cleaned[: parsed.max_text_bubbles], result

    fallback = fallback_bubbles(
        parsed,
        language=language,
        customer_name=customer_name,
        next_question=next_question,
        document_kind=document_kind,
        should_introduce=should_introduce,
    )
    fallback = validate_bubbles(fallback, language=language)
    result["fallback_used"] = True
    result["realized_acts"] = infer_realized_acts(fallback, parsed)
    logger.warning(
        "validate_dialogue_plan: violations=%s text=%r",
        result["violations"],
        joined[:200],
    )
    return fallback[: parsed.max_text_bubbles], result
