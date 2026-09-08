"""Follow-up outbound validator — invalid copy must not send.

Blocks pressure, invented finance, stale stock claims, re-introduction,
document obligation, full-funnel restart, and internal leaks. Unlike the
inbound response validator, this does not rewrite: empty or invalid output
is not sendable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from sdr.domain.dialogue_plan import contains_internal_leak, question_count
from sdr.domain.financial_promises import contains_forbidden_financial_promise
from sdr.domain.followup_plan import (
    FollowUpPlan,
    FollowUpStrategy,
    apply_current_inventory,
    resolved_vehicle_label,
)
from sdr.domain.introduction import is_first_contact_reopen
from sdr.domain.types import InventoryOutcome

_ABSENCE_SHAME = re.compile(
    r"vi\s+que\s+voc[eê]\s+sumiu|"
    r"voc[eê]\s+sumiu|"
    r"sumiu\s+daqui|"
    r"faz\s+tempo\s+que\s+n[aã]o\s+(?:fala|aparece)|"
    r"te\s+perdi|"
    r"sumiste",
    re.I,
)
_PRESSURE = re.compile(
    r"[uú]ltima\s+chance|"
    r"corre\s+que|"
    r"vai\s+acabar|"
    r"vai\s+embora|"
    r"n[aã]o\s+perca|"
    r"n[aã]o\s+perca\s+essa|"
    r"urgente|"
    r"agora\s+mesmo|"
    r"s[oó]\s+hoje|"
    r"restam?\s+apenas|"
    r"aproveita\s+(?:agora|hoje)|"
    r"vaga\s+limitad|"
    r"antes\s+que\s+acabe",
    re.I,
)
_DOCUMENT_OBLIGATION = re.compile(
    r"(?:precisa|precisa-se|obrigat[oó]rio|tem\s+que)\s+enviar|"
    r"sem\s+(?:os\s+)?documentos?\s+(?:n[aã]o|a\s+simula)|"
    r"manda\s+(?:agora\s+)?(?:os\s+)?documentos|"
    r"envie\s+agora\s+(?:os\s+)?documentos|"
    r"s[oó]\s+com\s+os\s+documentos",
    re.I,
)
_AVAILABILITY_CLAIM = re.compile(
    r"ainda\s+est[aá]\s+dispon[ií]vel|"
    r"est[aá]\s+dispon[ií]vel|"
    r"ainda\s+tem(?:os)?\b|"
    r"continua\s+dispon[ií]vel|"
    r"ainda\s+est[aá]\s+(?:no\s+)?estoque|"
    r"\bem\s+estoque\b|"
    r"segue\s+dispon[ií]vel|"
    r"continua\s+no\s+estoque",
    re.I,
)
_INTERNAL_EXTRA = re.compile(
    r"\b(?:lead|automa[cç][aã]o|automation|scheduler|follow-?up\s+job)\b",
    re.I,
)
_SUBSTITUTE_CTA = re.compile(
    r"que\s+tal\s+o\b|"
    r"te\s+mostro\s+(?:um\s+)?outr|"
    r"alternativa|"
    r"outro\s+(?:modelo|ve[ií]culo)|"
    r"em\s+vez\s+desse",
    re.I,
)
_FUNNEL_TOPICS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("deal_type", re.compile(r"compra\s+ou\s+troca|comprar,\s+vender|permuta", re.I)),
    ("payment", re.compile(r"[aà]\s+vista\s+ou\s+financiado", re.I)),
    ("documents", re.compile(r"envie\s+(?:a\s+)?cnh|comprovante\s+de\s+renda", re.I)),
    ("visit", re.compile(r"agendar\s+visita|que\s+dia.{0,24}visita", re.I)),
    ("vehicle_search", re.compile(r"o\s+que\s+voc[eê]\s+(?:est[aá]\s+)?(?:buscando|procurando)", re.I)),
)


@dataclass(slots=True)
class FollowUpValidation:
    sendable: bool
    bubbles: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sendable": self.sendable,
            "bubbles": list(self.bubbles),
            "violations": list(self.violations),
        }


def _fail(violations: list[str], code: str) -> None:
    if code not in violations:
        violations.append(code)


def _joined(bubbles: Sequence[str]) -> str:
    return " ".join(b.strip() for b in bubbles if isinstance(b, str) and b.strip())


def _clean_bubbles(bubbles: Sequence[str] | None) -> list[str]:
    return [b.strip() for b in (bubbles or []) if isinstance(b, str) and b.strip()]


def _availability_authorized(plan: FollowUpPlan) -> bool:
    if plan.strategy == FollowUpStrategy.CANCEL_SAFE.value:
        return False
    if plan.availability_detail in {"sold", "reserved"}:
        return False
    outcome = plan.inventory_outcome
    return outcome == InventoryOutcome.SUCCESS_FOUND.value


def validate_followup(
    bubbles: Sequence[str] | None,
    plan: FollowUpPlan,
    *,
    tool_results: Any = None,
) -> FollowUpValidation:
    """Return sendable bubbles or an empty non-sendable result."""
    bound = apply_current_inventory(plan, tool_results)
    cleaned = _clean_bubbles(bubbles)
    violations: list[str] = []

    if bound.strategy == FollowUpStrategy.DO_NOT_SEND.value:
        return FollowUpValidation(False, [], ["empty_plan"])

    if not cleaned:
        return FollowUpValidation(False, [], ["empty_output"])

    max_bubbles = bound.max_bubbles if bound.max_bubbles > 0 else 2
    if len(cleaned) > max_bubbles:
        _fail(violations, "too_many_bubbles")

    if question_count(cleaned) > 1:
        _fail(violations, "more_than_one_question")

    if is_first_contact_reopen(cleaned):
        _fail(violations, "reintroduction")

    joined = _joined(cleaned)

    if _ABSENCE_SHAME.search(joined):
        _fail(violations, "absence_shame")
    if _PRESSURE.search(joined):
        _fail(violations, "pressure")
    if _DOCUMENT_OBLIGATION.search(joined):
        _fail(violations, "document_obligation")
    if contains_forbidden_financial_promise(joined):
        _fail(violations, "financial_promise")
    if contains_internal_leak(joined) or _INTERNAL_EXTRA.search(joined):
        _fail(violations, "internal_leak")

    topics = [name for name, pattern in _FUNNEL_TOPICS if pattern.search(joined)]
    if len(topics) >= 2:
        _fail(violations, "full_funnel")

    if _AVAILABILITY_CLAIM.search(joined) and not _availability_authorized(bound):
        _fail(violations, "stale_or_unconfirmed_availability")

    if bound.strategy == FollowUpStrategy.CANCEL_SAFE.value:
        if _AVAILABILITY_CLAIM.search(joined):
            _fail(violations, "availability_after_sold")
        if _SUBSTITUTE_CTA.search(joined):
            _fail(violations, "auto_substitute")
        label = resolved_vehicle_label(bound)
        for alt in bound.alternative_labels:
            token = alt.strip()
            if not token:
                continue
            if label and token.lower() == label.lower():
                continue
            if re.search(re.escape(token), joined, re.I):
                _fail(violations, "auto_substitute")
                break

    last_question = bound.authorized_facts.get("last_assistant_question")
    if isinstance(last_question, str) and last_question.strip():
        normalized_last = " ".join(last_question.lower().split())
        if normalized_last and normalized_last == " ".join(joined.lower().split()):
            _fail(violations, "repeated_question")

    if violations:
        return FollowUpValidation(False, [], violations)
    return FollowUpValidation(True, cleaned[:max_bubbles], [])
