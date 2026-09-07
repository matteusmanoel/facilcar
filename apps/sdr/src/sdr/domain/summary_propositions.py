"""Authorized summary propositions and polarity validation.

The CRM narrative may only assert what these propositions encode.
Autodeclared claims_used is never sufficient — the final text is checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Proposition:
    entity: str
    attribute: str
    value: Any
    polarity: str = "asserted"  # asserted | negated | unknown
    modality: str = "fact"  # fact | preference | pending
    source: str = "canonical_state"
    scope: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "attribute": self.attribute,
            "value": self.value,
            "polarity": self.polarity,
            "modality": self.modality,
            "source": self.source,
            "scope": self.scope,
        }


def build_propositions(authorized: dict[str, Any]) -> list[Proposition]:
    """Deterministic authorized facts as explicit propositions."""
    props: list[Proposition] = []
    intent = str(authorized.get("intent") or "unknown")
    props.append(Proposition("conversation", "intent", intent))

    customer = authorized.get("customer_vehicle") if isinstance(
        authorized.get("customer_vehicle"), dict
    ) else {}
    desired = authorized.get("desired_vehicle") if isinstance(
        authorized.get("desired_vehicle"), dict
    ) else {}

    if desired.get("model") or desired.get("brand"):
        props.append(
            Proposition(
                "desired_vehicle",
                "identity",
                {
                    "brand": desired.get("brand"),
                    "model": desired.get("model"),
                    "year": desired.get("year"),
                },
            )
        )

    own_intents = {"trade", "sale", "consignment", "refinancing"}
    if intent in own_intents and (customer.get("model") or customer.get("brand")):
        props.append(
            Proposition(
                "customer_vehicle",
                "identity",
                {
                    "brand": customer.get("brand"),
                    "model": customer.get("model"),
                    "year": customer.get("year"),
                },
            )
        )
        fin = customer.get("financing_status")
        if fin:
            props.append(
                Proposition(
                    "customer_vehicle",
                    "financing_status",
                    fin,
                    polarity="asserted" if fin != "unknown" else "unknown",
                )
            )
        debt = authorized.get("debt_status") or customer.get("debt_status")
        if debt:
            props.append(
                Proposition(
                    "customer_vehicle",
                    "debt_status",
                    debt,
                    polarity="asserted" if debt != "unknown" else "unknown",
                )
            )

    pay = authorized.get("payment_method")
    applies = authorized.get("payment_applies_to")
    if pay:
        props.append(
            Proposition(
                "payment",
                "method",
                pay,
                scope=applies if isinstance(applies, str) else None,
            )
        )

    if authorized.get("price_expectation") not in (None, ""):
        props.append(
            Proposition(
                "customer_vehicle",
                "price_expectation",
                authorized.get("price_expectation"),
                modality="preference",
            )
        )

    deferred = list(authorized.get("documents_deferred") or []) or list(
        authorized.get("deferred_fields") or []
    )
    for name in deferred:
        props.append(
            Proposition("documents", name, "deferred", polarity="asserted", modality="pending")
        )
    missing = list(authorized.get("missing_fields") or [])
    for name in missing:
        if name in {"cnh", "proof_of_residence", "proof_of_income", "documents"}:
            props.append(
                Proposition("documents", name, "missing", polarity="asserted", modality="pending")
            )

    if authorized.get("visit_preferred_time"):
        props.append(
            Proposition(
                "visit",
                "preferred_at",
                authorized.get("visit_preferred_time"),
                modality="preference",
            )
        )
        if authorized.get("visit_pending_vendor_confirm"):
            props.append(
                Proposition("visit", "status", "pending_seller_confirmation", modality="pending")
            )

    props.append(
        Proposition("profile", "complete", bool(authorized.get("profile_complete")))
    )
    props.append(
        Proposition("profile", "handoff_ready", bool(authorized.get("handoff_ready")))
    )
    return props


def _prop(props: list[Proposition], entity: str, attribute: str) -> Proposition | None:
    for item in props:
        if item.entity == entity and item.attribute == attribute:
            return item
    return None


_FINANCED_NOW = re.compile(
    r"est[aá]\s+financiado|possui financiamento em aberto|com financiamento em aberto|"
    r"ve[ií]culo.{0,24}financiado|(?:o|a|seu|sua)\s+\w+\s+est[aá]\s+financiado",
    re.I,
)
_PAID_OFF = re.compile(r"\bquitado\b|\bquita\b", re.I)
_NO_DEBT = re.compile(r"sem\s+d[eé]bitos|sem\s+d[ií]vidas|n[aã]o\s+tem\s+d[eé]bitos", re.I)
_HAS_DEBT = re.compile(r"d[eé]bitos?\s+pendentes|est[aá]\s+financiado.{0,10}d[eé]bito", re.I)
_STORE_APPRAISAL = re.compile(
    r"\bavalia[çc][aã]o da loja\b|\bavaliado em\b|\bvale\s+r\$|\best[aá]\s+avaliado\b",
    re.I,
)
_VISIT_CONFIRMED = re.compile(
    r"visita\s+(foi\s+)?agendada|visita\s+confirmada|agendou\s+(uma\s+)?visita|"
    r"hor[aá]rio confirmado",
    re.I,
)
_CASH_OR_FINANCE = re.compile(
    r"pagar ou financiar|financiar a diferen[çc]a em dinheiro|"
    r"pagar ou financiar a diferen[çc]a em dinheiro",
    re.I,
)
_WHOLE_CASH = re.compile(r"opera[çc][aã]o.{0,20}[aà]\s+vista|tudo\s+[aà]\s+vista", re.I)
_CLIENT_DEBTS_ABSENCE = re.compile(
    r"n[aã]o h[aá] informa[çc][oõ]es sobre as d[ií]vidas|"
    r"d[ií]vidas do cliente|d[eé]bitos do cliente",
    re.I,
)
_DOCS_READY = re.compile(
    r"documentos?\s+\w*\s*(prontos?|recebidos?|enviados?)|"
    r"(prontos?|recebidos?|enviados?)\s+\w*\s*documentos?|"
    r"documentos necessários.{0,40}prontos",
    re.I,
)
_NO_VISIT = re.compile(r"n[aã]o\s+(h[aá]|tem)\s+.{0,10}visita|visita n[aã]o (foi )?discut", re.I)


def detect_claims(text: str) -> list[dict[str, Any]]:
    """Surface-level claims found in the narrative, for the report."""
    low = text or ""
    found: list[dict[str, Any]] = []
    if _FINANCED_NOW.search(low):
        found.append({"attribute": "financing_status", "value": "financed", "span": "financiado"})
    if _PAID_OFF.search(low):
        found.append({"attribute": "financing_status", "value": "paid_off", "span": "quitado"})
    if _NO_DEBT.search(low):
        found.append({"attribute": "debt_status", "value": "clear", "span": "sem débitos"})
    if _STORE_APPRAISAL.search(low):
        found.append({"attribute": "price_expectation", "value": "store_appraisal", "span": "avaliação"})
    if _VISIT_CONFIRMED.search(low):
        found.append({"attribute": "visit", "value": "confirmed", "span": "agendada"})
    if _CASH_OR_FINANCE.search(low):
        found.append({"attribute": "payment_method", "value": "ambiguous_cash_finance"})
    return found


def validate_text_against_propositions(
    text: str,
    authorized: dict[str, Any],
    propositions: list[Proposition] | None = None,
) -> dict[str, Any]:
    """Independent polarity/role check. Does not trust claims_used."""
    props = propositions if propositions is not None else build_propositions(authorized)
    violations: list[str] = []
    low = text or ""
    intent = str(authorized.get("intent") or "")
    claims = detect_claims(low)

    fin = _prop(props, "customer_vehicle", "financing_status")
    if fin and fin.value == "paid_off" and _FINANCED_NOW.search(low) and not _PAID_OFF.search(low):
        violations.append("paid_off_described_as_financed")
    if fin and fin.value == "financed" and _PAID_OFF.search(low) and "financiamento quitado" not in low.lower():
        violations.append("financed_described_as_paid_off")

    debt = _prop(props, "customer_vehicle", "debt_status")
    debt_val = (debt.value if debt else None) or authorized.get("debt_status")
    if debt_val in {"has_debts", "partial", "unknown", None} and _NO_DEBT.search(low):
        if debt_val != "clear":
            violations.append("debts_described_as_clear")
    if debt_val == "has_debts" and _NO_DEBT.search(low):
        violations.append("has_debts_described_as_clear")
    if debt_val == "partial" and re.search(r"sem d[eé]bitos|d[eé]bitos resolvidos|tudo em dia", low, re.I):
        violations.append("partial_debts_described_as_resolved")

    if authorized.get("price_expectation") not in (None, "") and _STORE_APPRAISAL.search(low):
        violations.append("expectation_described_as_store_appraisal")

    if authorized.get("visit_pending_vendor_confirm") and _VISIT_CONFIRMED.search(low):
        violations.append("visit_described_as_confirmed")

    applies = authorized.get("payment_applies_to")
    pay = str(authorized.get("payment_method") or "").lower()
    if applies == "difference" and pay == "cash":
        if _CASH_OR_FINANCE.search(low):
            violations.append("difference_cash_ambiguous_wording")
        if _WHOLE_CASH.search(low):
            violations.append("difference_cash_described_as_whole_deal")
        if re.search(r"diferen", low, re.I) and re.search(r"em dinheiro", low, re.I) and not re.search(
            r"[aà]\s+vista", low, re.I
        ):
            violations.append("difference_cash_described_as_money_ambiguous")
    if applies == "difference" and pay == "financing":
        if re.search(r"diferen[çc]a [aà] vista|pagar a diferen[çc]a [aà] vista", low, re.I):
            violations.append("difference_financing_described_as_cash")
        if _CASH_OR_FINANCE.search(low):
            violations.append("difference_financing_ambiguous_wording")

    deferred = [
        p.attribute
        for p in props
        if p.entity == "documents" and p.value == "deferred"
    ]
    if deferred and _DOCS_READY.search(low):
        violations.append("deferred_documents_described_as_ready")

    docs_applicable = intent in {"purchase_financing", "trade"} and (
        intent == "purchase_financing"
        or (intent == "trade" and pay == "financing" and applies == "difference")
    )
    if not docs_applicable and re.search(r"\bdocumentos?\b", low, re.I):
        if intent in {"purchase", "sale", "consignment"} or (
            intent == "trade" and applies != "difference"
        ):
            if intent == "purchase":
                violations.append("inapplicable_documents_in_purchase_summary")

    if intent in {"purchase", "purchase_financing"} and _CLIENT_DEBTS_ABSENCE.search(low):
        violations.append("inapplicable_client_debts_in_purchase_summary")

    if intent == "purchase" and re.search(
        r"financiamento (em aberto|do ve[ií]culo)|ve[ií]culo pr[oó]prio", low, re.I
    ):
        violations.append("inapplicable_own_vehicle_finance_in_purchase")

    if intent == "refinancing" and not authorized.get("visit_preferred_time") and _NO_VISIT.search(low):
        violations.append("refinancing_invented_visit_absence")

    if intent == "sale" and re.search(r"\btroca\b|\btrocar\b|\bpermuta\b", low, re.I):
        violations.append("sale_summary_mentions_trade")

    return {
        "pass": not violations,
        "violations": violations,
        "claims": claims,
        "propositions": [p.as_dict() for p in props],
        "invariants_executed": [
            "financing_polarity",
            "debt_polarity",
            "expectation_not_appraisal",
            "visit_not_confirmed",
            "difference_payment_wording",
            "documents_polarity",
            "intent_scoped_facts",
        ],
    }
