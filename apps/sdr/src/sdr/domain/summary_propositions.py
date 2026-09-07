"""Authorized summary propositions and polarity validation.

The CRM narrative may only assert what these propositions encode.
A factual summary with no extracted claims is a validation failure —
empty claims is not absence of violation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sdr.domain.summary_labels import DOCUMENT_LABELS, format_money


@dataclass
class Proposition:
    id: str
    entity: str
    attribute: str
    value: Any
    polarity: str = "asserted"  # asserted | negated | unknown
    modality: str = "fact"  # fact | preference | pending
    source: str = "canonical_state"
    scope: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity": self.entity,
            "attribute": self.attribute,
            "value": self.value,
            "polarity": self.polarity,
            "modality": self.modality,
            "source": self.source,
            "scope": self.scope,
        }


def _pid(entity: str, attribute: str, extra: str | None = None) -> str:
    return f"{entity}.{attribute}" + (f".{extra}" if extra else "")


def documents_applicable_for(authorized: dict[str, Any]) -> bool:
    intent = str(authorized.get("intent") or "")
    if authorized.get("documents_applicable") is False:
        return False
    if authorized.get("documents_applicable") is True:
        return True
    pay = str(authorized.get("payment_method") or "").lower()
    applies = authorized.get("payment_applies_to")
    if intent == "purchase_financing":
        return True
    if intent == "trade" and pay == "financing" and applies == "difference":
        return True
    return False


def build_propositions(authorized: dict[str, Any]) -> list[Proposition]:
    """Deterministic authorized facts as explicit propositions."""
    props: list[Proposition] = []
    intent = str(authorized.get("intent") or "unknown")
    props.append(Proposition(_pid("conversation", "intent"), "conversation", "intent", intent))

    name = (authorized.get("name") or "").strip() or None
    if name:
        props.append(Proposition(_pid("customer", "name"), "customer", "name", name))

    customer = authorized.get("customer_vehicle") if isinstance(
        authorized.get("customer_vehicle"), dict
    ) else {}
    desired = authorized.get("desired_vehicle") if isinstance(
        authorized.get("desired_vehicle"), dict
    ) else {}

    def _identity(entity: str, vehicle: dict[str, Any]) -> None:
        identity: dict[str, Any] = {}
        for key in ("brand", "model", "year", "color"):
            if vehicle.get(key) not in (None, ""):
                identity[key] = vehicle.get(key)
                props.append(
                    Proposition(_pid(entity, key), entity, key, vehicle.get(key))
                )
        if vehicle.get("mileage") not in (None, ""):
            identity["mileage"] = vehicle.get("mileage")
            props.append(
                Proposition(_pid(entity, "mileage"), entity, "mileage", vehicle.get("mileage"))
            )
        if identity:
            props.append(Proposition(_pid(entity, "identity"), entity, "identity", identity))

    if desired.get("model") or desired.get("brand"):
        _identity("desired_vehicle", desired)

    own_intents = {"trade", "sale", "consignment", "refinancing"}
    if intent in own_intents and (customer.get("model") or customer.get("brand")):
        _identity("customer_vehicle", customer)
        fin = customer.get("financing_status") or authorized.get("financing_status")
        if fin:
            props.append(
                Proposition(
                    _pid("customer_vehicle", "financing_status"),
                    "customer_vehicle",
                    "financing_status",
                    fin,
                    polarity="asserted" if fin != "unknown" else "unknown",
                )
            )
        rem = customer.get("installments_remaining")
        if rem not in (None, ""):
            props.append(
                Proposition(
                    _pid("customer_vehicle", "installments_remaining"),
                    "customer_vehicle",
                    "installments_remaining",
                    rem,
                )
            )
        inst = customer.get("installment_value")
        if inst not in (None, ""):
            props.append(
                Proposition(
                    _pid("customer_vehicle", "installment_value"),
                    "customer_vehicle",
                    "installment_value",
                    inst,
                )
            )
        debt = authorized.get("debt_status") or customer.get("debt_status")
        if debt:
            props.append(
                Proposition(
                    _pid("customer_vehicle", "debt_status"),
                    "customer_vehicle",
                    "debt_status",
                    debt,
                    polarity="asserted" if debt != "unknown" else "unknown",
                )
            )
        types = authorized.get("debt_types") or customer.get("debt_types")
        if types and str(types).lower() not in {"sem_multas", "sem multa"}:
            props.append(
                Proposition(
                    _pid("customer_vehicle", "debt_types"),
                    "customer_vehicle",
                    "debt_types",
                    types,
                )
            )

    pay = authorized.get("payment_method")
    applies = authorized.get("payment_applies_to")
    if pay:
        props.append(
            Proposition(
                _pid("payment", "method"),
                "payment",
                "method",
                pay,
                scope=applies if isinstance(applies, str) else None,
            )
        )
    if applies:
        props.append(
            Proposition(_pid("payment", "scope"), "payment", "scope", applies)
        )

    if authorized.get("down_payment") not in (None, ""):
        props.append(
            Proposition(
                _pid("payment", "down_payment"),
                "payment",
                "down_payment",
                authorized.get("down_payment"),
            )
        )
    if authorized.get("desired_installment") not in (None, ""):
        props.append(
            Proposition(
                _pid("payment", "desired_installment"),
                "payment",
                "desired_installment",
                authorized.get("desired_installment"),
            )
        )

    if authorized.get("price_expectation") not in (None, ""):
        props.append(
            Proposition(
                _pid("customer_vehicle", "price_expectation"),
                "customer_vehicle",
                "price_expectation",
                authorized.get("price_expectation"),
                modality="preference",
            )
        )

    if authorized.get("amount_needed") not in (None, ""):
        props.append(
            Proposition(
                _pid("refinancing", "amount_needed"),
                "refinancing",
                "amount_needed",
                authorized.get("amount_needed"),
            )
        )

    if authorized.get("leave_at_store") not in (None, ""):
        props.append(
            Proposition(
                _pid("consignment", "leave_at_store"),
                "consignment",
                "leave_at_store",
                authorized.get("leave_at_store"),
            )
        )

    docs_ok = documents_applicable_for(authorized)
    if docs_ok:
        deferred = list(authorized.get("documents_deferred") or [])
        status = authorized.get("document_status") if isinstance(
            authorized.get("document_status"), dict
        ) else {}
        received_keys = [
            k for k, v in status.items() if v == "received"
        ]
        if authorized.get("documents_received") and not received_keys:
            props.append(
                Proposition(_pid("documents", "pack"), "documents", "pack", "received")
            )
        for name in received_keys:
            props.append(
                Proposition(
                    _pid("documents", name),
                    "documents",
                    name,
                    "received",
                    polarity="asserted",
                )
            )
        for name in deferred:
            props.append(
                Proposition(
                    _pid("documents", name),
                    "documents",
                    name,
                    "deferred",
                    polarity="asserted",
                    modality="pending",
                )
            )
        missing = list(authorized.get("missing_fields") or [])
        for name in missing:
            if name in {"cnh", "proof_of_residence", "proof_of_income", "documents"}:
                props.append(
                    Proposition(
                        _pid("documents", name),
                        "documents",
                        name,
                        "missing",
                        polarity="asserted",
                        modality="pending",
                    )
                )

    if authorized.get("visit_preferred_time"):
        props.append(
            Proposition(
                _pid("visit", "preferred_at"),
                "visit",
                "preferred_at",
                authorized.get("visit_preferred_time"),
                modality="preference",
            )
        )
        if authorized.get("visit_pending_vendor_confirm"):
            props.append(
                Proposition(
                    _pid("visit", "status"),
                    "visit",
                    "status",
                    "pending_seller_confirmation",
                    modality="pending",
                )
            )

    props.append(
        Proposition(
            _pid("profile", "complete"),
            "profile",
            "complete",
            bool(authorized.get("profile_complete")),
        )
    )
    if authorized.get("handoff_reason"):
        props.append(
            Proposition(
                _pid("handoff", "reason"),
                "handoff",
                "reason",
                authorized.get("handoff_reason"),
            )
        )
    props.append(
        Proposition(
            _pid("profile", "handoff_ready"),
            "profile",
            "handoff_ready",
            bool(authorized.get("handoff_ready")),
        )
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
_NO_DEBT = re.compile(
    r"sem\s+d[eé]bitos|sem\s+d[ií]vidas|n[aã]o\s+tem\s+d[eé]bitos|sem d[eé]bitos informados",
    re.I,
)
_HAS_DEBT = re.compile(r"d[eé]bitos?\s+pendentes|com d[eé]bitos", re.I)
_STORE_APPRAISAL = re.compile(
    r"\bavalia[çc][aã]o da loja\b|\bavaliado em\b|\bvale\s+r\$|\best[aá]\s+avaliado\b"
    r"|\bavalia[çc][aã]o de\s+r\$",
    re.I,
)
_VISIT_CONFIRMED = re.compile(
    r"visita\s+(foi\s+)?agendada|visita\s+confirmada|agendou\s+(uma\s+)?visita|"
    r"hor[aá]rio confirmado|est[aá]\s+marcada|ficou\s+marcada|"
    r"visita\s+est[aá]\s+marcada|visita\s+marcada|hor[aá]rio marcado|"
    r"visita garantida|reserva confirmada|\bmarcada para\b",
    re.I,
)
_VISIT_PENDING = re.compile(
    r"prefer[eê]ncia de visita|hor[aá]rio pretendido|op[cç][aã]o escolhida|"
    r"pendente de confirma[cç][aã]o|vendedor confirmar",
    re.I,
)
_CASH_OR_FINANCE = re.compile(
    r"pagar ou financiar|financiar a diferen[çc]a em dinheiro|"
    r"pagar ou financiar a diferen[çc]a em dinheiro",
    re.I,
)
_WHOLE_CASH = re.compile(r"opera[çc][aã]o.{0,20}[aà]\s+vista|tudo\s+[aà]\s+vista", re.I)
_DIFF_CASH = re.compile(r"diferen[çc]a [aà] vista|pagar a diferen[çc]a [aà] vista", re.I)
_DIFF_FIN = re.compile(r"financiar a diferen[çc]a|diferen[çc]a financiada", re.I)
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
_DOCS_DEFERRED = re.compile(
    r"envio posterior|ficaram para envio|adiad|documentos?.{0,24}depois",
    re.I,
)
_NO_VISIT = re.compile(
    r"n[aã]o\s+(h[aá]|tem)\s+.{0,10}visita|visita n[aã]o (foi )?discut|"
    r"sem.{0,20}confirma[cç][aã]o de visita|sem pend[eê]ncias.{0,40}visita",
    re.I,
)
_NO_DOC_PENDING = re.compile(
    r"sem pend[eê]ncias de documentos|sem pend[eê]ncias de documentos ou|"
    r"documentos?.{0,16}em dia|n[aã]o (h[aá]|tem) pend[eê]ncia.{0,20}documento",
    re.I,
)
_PROFILE_COMPLETE = re.compile(r"perfil completo|perfil est[aá] completo", re.I)
_PROFILE_INCOMPLETE = re.compile(
    r"perfil (ainda )?(incompleto|precisa ser complementado)|ainda precisa ser complementado",
    re.I,
)
_INTENT_TRADE = re.compile(r"\btrocar\b|\btroca\b|\bpermuta\b", re.I)
_INTENT_SALE = re.compile(r"\bvender\b|\bvenda\b", re.I)
_INTENT_CONSIGN = re.compile(r"consign", re.I)
_INTENT_REFIN = re.compile(r"refinanc", re.I)
_INTENT_PURCHASE = re.compile(r"\bcomprar\b|\bcompra\b", re.I)
_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
_KM = re.compile(r"(\d[\d.]*)\s*(?:mil\s+)?km", re.I)
_PARCELAS = re.compile(r"(\d+)\s+parcelas?(?!\s+desejad)", re.I)
_PARCELA_VALUE = re.compile(
    r"(?:parcelas?\s+(?:restantes\s+)?de\s+)?r\$\s*([\d.]+)",
    re.I,
)
_COLORS = ("branco", "preto", "prata", "vermelho", "cinza", "azul", "verde")


def text_has_factual_assertions(text: str) -> bool:
    """True when the narrative asserts commercial facts that must be claimed."""
    low = text or ""
    if re.search(
        r"r\$|\bquitado\b|\bfinanciado\b|\bdocumentos?\b|\bvisita\b|"
        r"\bd[eé]bitos?\b|\bparcelas?\b|\bkm\b|\b(?:19|20)\d{2}\b|"
        r"comprovante|cnh|\bexpectativa\b|\bavaliad|\bmarcada\b|"
        r"perfil (in)?completo",
        low,
        re.I,
    ):
        return True
    if re.search(
        r"\b(comprar|compra|trocar|troca|vender|venda|consign|refinanc)\b",
        low,
        re.I,
    ):
        return True
    return False


def detect_claims(text: str, authorized: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Extract verifiable claims from the narrative."""
    low = text or ""
    auth = authorized or {}
    found: list[dict[str, Any]] = []

    name = str(auth.get("name") or "").strip()
    if name and name.lower() in low.lower():
        found.append({
            "entity": "customer",
            "attribute": "name",
            "value": name,
            "span": name,
        })

    if _INTENT_CONSIGN.search(low):
        found.append({"entity": "conversation", "attribute": "intent", "value": "consignment", "span": "consign"})
    elif _INTENT_REFIN.search(low):
        found.append({"entity": "conversation", "attribute": "intent", "value": "refinancing", "span": "refinanci"})
    elif _INTENT_TRADE.search(low):
        found.append({"entity": "conversation", "attribute": "intent", "value": "trade", "span": "troca"})
    elif _INTENT_SALE.search(low):
        found.append({"entity": "conversation", "attribute": "intent", "value": "sale", "span": "venda"})
    elif _INTENT_PURCHASE.search(low):
        value = "purchase_financing" if re.search(r"financi", low, re.I) and "diferen" not in low.lower() else "purchase"
        if re.search(r"via financiamento|compra financiada|comprando via", low, re.I):
            value = "purchase_financing"
        found.append({"entity": "conversation", "attribute": "intent", "value": value, "span": "compra"})

    def _vehicle_claims(entity: str, vehicle: dict[str, Any]) -> None:
        for key in ("brand", "model"):
            token = str(vehicle.get(key) or "").strip()
            if token and token.lower() in low.lower():
                found.append({"entity": entity, "attribute": key, "value": token, "span": token})
        year = str(vehicle.get("year") or "").strip()
        if year and re.search(rf"\b{re.escape(year)}\b", low):
            found.append({"entity": entity, "attribute": "year", "value": year, "span": year})
        color = str(vehicle.get("color") or "").strip()
        if color and color.lower() in low.lower():
            found.append({"entity": entity, "attribute": "color", "value": color, "span": color})
        mileage = vehicle.get("mileage")
        if mileage not in (None, "") and re.search(r"\bkm\b", low, re.I):
            found.append({"entity": entity, "attribute": "mileage", "value": mileage, "span": "km"})

    desired = auth.get("desired_vehicle") if isinstance(auth.get("desired_vehicle"), dict) else {}
    customer = auth.get("customer_vehicle") if isinstance(auth.get("customer_vehicle"), dict) else {}
    _vehicle_claims("desired_vehicle", desired)
    _vehicle_claims("customer_vehicle", customer)

    if _PAID_OFF.search(low):
        found.append({
            "entity": "customer_vehicle",
            "attribute": "financing_status",
            "value": "paid_off",
            "span": "veículo quitado" if "veículo quitado" in low.lower() or "veiculo quitado" in low.lower() else "quitado",
        })
    if _FINANCED_NOW.search(low):
        found.append({
            "entity": "customer_vehicle",
            "attribute": "financing_status",
            "value": "financed",
            "span": "financiado",
        })

    rem = _PARCELAS.search(low)
    if rem:
        found.append({
            "entity": "customer_vehicle",
            "attribute": "installments_remaining",
            "value": int(rem.group(1)),
            "span": rem.group(0),
        })
    inst = customer.get("installment_value") if customer else None
    if inst not in (None, "") and format_money(inst) and format_money(inst) in (text or ""):
        found.append({
            "entity": "customer_vehicle",
            "attribute": "installment_value",
            "value": inst,
            "span": format_money(inst),
        })
    elif inst not in (None, "") and re.search(rf"r\$\s*{int(float(inst))}", low.replace(".", ""), re.I):
        found.append({
            "entity": "customer_vehicle",
            "attribute": "installment_value",
            "value": inst,
            "span": str(inst),
        })

    if _NO_DEBT.search(low):
        found.append({
            "entity": "customer_vehicle",
            "attribute": "debt_status",
            "value": "clear",
            "span": "sem débitos",
        })
    elif _HAS_DEBT.search(low):
        found.append({
            "entity": "customer_vehicle",
            "attribute": "debt_status",
            "value": "has_debts",
            "span": "débitos",
        })

    if _STORE_APPRAISAL.search(low):
        found.append({
            "entity": "customer_vehicle",
            "attribute": "price_role",
            "value": "store_appraisal",
            "span": "avaliação",
        })
    elif auth.get("price_expectation") not in (None, "") and re.search(
        r"espera|expectativa|aproximadamente", low, re.I
    ):
        found.append({
            "entity": "customer_vehicle",
            "attribute": "price_expectation",
            "value": auth.get("price_expectation"),
            "span": "espera",
        })

    if auth.get("amount_needed") not in (None, "") and re.search(
        r"necessidade|precisa|levantar", low, re.I
    ):
        found.append({
            "entity": "refinancing",
            "attribute": "amount_needed",
            "value": auth.get("amount_needed"),
            "span": "necessidade",
        })

    if _DIFF_CASH.search(low):
        found.append({"entity": "payment", "attribute": "method", "value": "cash", "span": "diferença à vista"})
        found.append({"entity": "payment", "attribute": "scope", "value": "difference", "span": "diferença"})
    elif _DIFF_FIN.search(low):
        found.append({"entity": "payment", "attribute": "method", "value": "financing", "span": "diferença financiada"})
        found.append({"entity": "payment", "attribute": "scope", "value": "difference", "span": "diferença"})
    if _CASH_OR_FINANCE.search(low):
        found.append({"entity": "payment", "attribute": "method", "value": "ambiguous_cash_finance", "span": "pagar ou financiar"})

    desired_inst = auth.get("desired_installment")
    if desired_inst not in (None, "") and (
        re.search(r"parcela desejada", low, re.I)
        or (format_money(desired_inst) and format_money(desired_inst) in (text or ""))
    ):
        found.append({
            "entity": "payment",
            "attribute": "desired_installment",
            "value": desired_inst,
            "span": "parcela desejada",
        })

    if auth.get("down_payment") not in (None, "") and re.search(r"\bentrada\b", low, re.I):
        found.append({
            "entity": "payment",
            "attribute": "down_payment",
            "value": auth.get("down_payment"),
            "span": "entrada",
        })

    if _DOCS_DEFERRED.search(low):
        for key, label in DOCUMENT_LABELS.items():
            if key == "documents":
                continue
            if label.lower() in low.lower() or key in low:
                found.append({
                    "entity": "documents",
                    "attribute": key,
                    "value": "deferred",
                    "span": label,
                })
        if not any(c.get("entity") == "documents" for c in found):
            found.append({"entity": "documents", "attribute": "pack", "value": "deferred", "span": "envio posterior"})
    if _DOCS_READY.search(low):
        found.append({"entity": "documents", "attribute": "pack", "value": "received", "span": "documentos recebidos"})
    if re.search(r"documentos?\s+n[aã]o recebidos|documentos?\s+ausentes|sem os documentos", low, re.I):
        found.append({"entity": "documents", "attribute": "pack", "value": "missing", "span": "documentos não recebidos"})
    if _NO_DOC_PENDING.search(low):
        found.append({"entity": "documents", "attribute": "pendency", "value": "none", "span": "sem pendências de documentos"})

    if _VISIT_CONFIRMED.search(low):
        found.append({"entity": "visit", "attribute": "status", "value": "confirmed", "span": "marcada"})
    elif _VISIT_PENDING.search(low) or re.search(r"prefer[eê]ncia de visita", low, re.I):
        found.append({
            "entity": "visit",
            "attribute": "status",
            "value": "pending_seller_confirmation",
            "span": "preferência de visita",
        })
    if auth.get("visit_preferred_time") and str(auth.get("visit_preferred_time"))[:5].lower() in low.lower():
        found.append({
            "entity": "visit",
            "attribute": "preferred_at",
            "value": auth.get("visit_preferred_time"),
            "span": "visita",
        })

    if _PROFILE_COMPLETE.search(low):
        found.append({"entity": "profile", "attribute": "complete", "value": True, "span": "perfil completo"})
    if _PROFILE_INCOMPLETE.search(low):
        found.append({"entity": "profile", "attribute": "complete", "value": False, "span": "perfil incompleto"})

    if re.search(r"encaminh", low, re.I):
        found.append({"entity": "handoff", "attribute": "reason", "value": "handoff", "span": "encaminhado"})

    return found


def _values_compatible(prop_value: Any, claim_value: Any) -> bool:
    if claim_value == "ambiguous_cash_finance":
        return False
    if claim_value == "store_appraisal":
        return False
    if claim_value == "confirmed" and prop_value == "pending_seller_confirmation":
        return False
    if isinstance(prop_value, bool) or isinstance(claim_value, bool):
        return bool(prop_value) == bool(claim_value)
    if isinstance(prop_value, (int, float)) or isinstance(claim_value, (int, float)):
        try:
            return int(float(prop_value)) == int(float(claim_value))
        except (TypeError, ValueError):
            return False
    return str(prop_value).strip().lower() == str(claim_value).strip().lower()


def link_claims_to_propositions(
    claims: list[dict[str, Any]],
    propositions: list[Proposition],
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for claim in claims:
        match = False
        authorized_by = None
        entity = claim.get("entity")
        attr = claim.get("attribute")
        value = claim.get("value")
        if attr == "price_role" and value == "store_appraisal":
            links.append({"claim": claim, "authorized_by": None, "match": False})
            continue
        if entity == "documents" and attr == "pendency" and value == "none":
            links.append({"claim": claim, "authorized_by": None, "match": False})
            continue
        if entity == "handoff" and attr == "reason":
            handoff = _prop(propositions, "handoff", "reason") or _prop(
                propositions, "profile", "handoff_ready"
            )
            if handoff and (handoff.value not in (None, "", False)):
                links.append({"claim": claim, "authorized_by": handoff.id, "match": True})
                continue
        for prop in propositions:
            if prop.entity != entity:
                continue
            if prop.attribute != attr and not (
                attr == "identity" and prop.attribute in {"brand", "model", "year"}
            ):
                if entity == "documents" and attr == "pack" and prop.entity == "documents":
                    if _values_compatible(prop.value, value):
                        match = True
                        authorized_by = prop.id
                        break
                continue
            if prop.attribute == attr and _values_compatible(prop.value, value):
                match = True
                authorized_by = prop.id
                break
        # Intent: purchase vs purchase_financing is compatible one way.
        if not match and entity == "conversation" and attr == "intent":
            intent_prop = _prop(propositions, "conversation", "intent")
            if intent_prop and str(intent_prop.value) == str(value):
                match = True
                authorized_by = intent_prop.id
            elif intent_prop and {str(intent_prop.value), str(value)} <= {
                "purchase",
                "purchase_financing",
            }:
                match = True
                authorized_by = intent_prop.id
        links.append({"claim": claim, "authorized_by": authorized_by, "match": match})
    return links


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
    claims = detect_claims(low, authorized)
    links = link_claims_to_propositions(claims, props)

    if text_has_factual_assertions(low) and not claims:
        violations.append("factual_summary_without_extracted_claims")

    for link in links:
        if not link.get("match"):
            claim = link.get("claim") or {}
            violations.append(
                f"unauthorized_claim:{claim.get('entity')}.{claim.get('attribute')}={claim.get('value')}"
            )

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

    docs_applicable = documents_applicable_for(authorized)
    if not docs_applicable and re.search(r"\bdocumentos?\b|comprovante de (resid|renda)|\bcnh\b", low, re.I):
        if intent in {"purchase", "sale", "consignment", "refinancing"} or (
            intent == "trade" and applies != "difference"
        ):
            violations.append("inapplicable_documents_in_summary")
            if intent == "purchase":
                violations.append("inapplicable_documents_in_purchase_summary")

    if intent in {"purchase", "purchase_financing"} and _CLIENT_DEBTS_ABSENCE.search(low):
        violations.append("inapplicable_client_debts_in_purchase_summary")

    if intent == "purchase" and re.search(
        r"financiamento (em aberto|do ve[ií]culo)|ve[ií]culo pr[oó]prio", low, re.I
    ):
        violations.append("inapplicable_own_vehicle_finance_in_purchase")

    if intent == "purchase" and (_NO_DEBT.search(low) or _HAS_DEBT.search(low)):
        violations.append("inapplicable_debts_in_purchase_summary")

    if intent == "refinancing" and not authorized.get("visit_preferred_time") and (
        _NO_VISIT.search(low) or re.search(r"\bvisita\b", low, re.I)
    ):
        violations.append("refinancing_invented_visit_absence")

    if intent == "refinancing" and not docs_applicable and _NO_DOC_PENDING.search(low):
        violations.append("refinancing_invented_document_absence")

    if intent == "sale" and re.search(r"\btroca\b|\btrocar\b|\bpermuta\b", low, re.I):
        violations.append("sale_summary_mentions_trade")

    if re.search(r"parcela\(s\)", low, re.I):
        violations.append("internal_pluralization_exposed")
    if re.search(r"proof_of_residence|proof_of_income", low):
        violations.append("internal_document_field_exposed")

    return {
        "pass": not violations,
        "violations": violations,
        "claims": claims,
        "claim_links": links,
        "propositions": [p.as_dict() for p in props],
        "invariants_executed": [
            "financing_polarity",
            "debt_polarity",
            "expectation_not_appraisal",
            "visit_not_confirmed",
            "difference_payment_wording",
            "documents_polarity",
            "intent_scoped_facts",
            "claims_extracted",
            "claims_authorized",
        ],
    }
