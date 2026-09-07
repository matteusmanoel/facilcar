"""Vendor-facing CRM summary — deterministic projection of canonical state.

The admin "Resumo da Júlia" and the WhatsApp handoff confirmation share this
builder. Canonical enums and raw facts stay in metadataJson / structured tables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sdr.domain.authorized_facts import build_authorized_facts
from sdr.domain.summary_propositions import (
    build_propositions,
    validate_text_against_propositions,
)
from sdr.domain.types import ConversationCanonicalState
from sdr.domain.vehicle_catalog import brands_compatible


def is_placeholder_display_name(name: str | None) -> bool:
    value = (name or "").strip()
    return not value or value.lower().startswith("whatsapp ")


def _forma_comercial(state: ConversationCanonicalState) -> str | None:
    payment = str(state.facts.get("payment_method") or "").strip().lower()
    deal = str(state.facts.get("deal_type") or "").strip().lower()
    if state.intent.value == "purchase_financing" or payment == "financing":
        return "Compra financiada"
    if payment in {"cash", "a_vista", "à vista"}:
        return "Compra à vista"
    deal_map = {
        "purchase": "Compra à vista",
        "financing": "Compra financiada",
        "trade": "Troca",
        "sale": "Venda",
        "consignment": "Consignação",
        "refinancing": "Refinanciamento",
    }
    if deal:
        return deal_map.get(deal, deal)
    if state.intent.value == "purchase":
        return "Compra"
    return None


def _compute_age(birth_date_str: str | None) -> int | None:
    """Return age in years from a birth date string (DD/MM/AAAA or AAAA-MM-DD)."""
    if not birth_date_str:
        return None
    try:
        text = birth_date_str.strip()
        # Try BR format: DD/MM/AAAA
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            # Try ISO: AAAA-MM-DD
            m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
            if not m2:
                return None
            year, month, day = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        today = date.today()
        age = today.year - year - ((today.month, today.day) < (month, day))
        return age if 0 < age < 130 else None
    except Exception:
        return None


@dataclass
class VendorSummaryResult:
    text: str
    authorized: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    used_llm: bool = False
    used_fallback: bool = False
    llm_rejected: bool = False
    propositions: list[dict[str, Any]] = field(default_factory=list)


def build_vendor_summary(state: ConversationCanonicalState) -> str:
    """Human-readable narrative brief for the seller (CRM and handoff confirmation)."""
    return compose_vendor_summary(state).text


def compose_vendor_summary(state: ConversationCanonicalState) -> VendorSummaryResult:
    auth = build_authorized_facts(state)
    payload = auth.as_dict()
    propositions = [p.as_dict() for p in build_propositions(payload)]
    deterministic = _build_vendor_summary_deterministic(state)
    if _is_empty_vendor_request(state):
        text = _empty_vendor_request_summary(state)
        validation = validate_summary_against_authorized(text, payload)
        return VendorSummaryResult(
            text=text,
            authorized=payload,
            validation=validation,
            used_fallback=False,
            propositions=propositions,
        )
    llm_text = None
    if _vendor_summary_llm_allowed():
        try:
            llm_text = _build_vendor_summary_llm(payload)
        except Exception:
            llm_text = None
    if llm_text:
        validation = validate_summary_against_authorized(llm_text, payload)
        if validation.get("pass"):
            return VendorSummaryResult(
                text=llm_text,
                authorized=payload,
                validation=validation,
                used_llm=True,
                propositions=propositions,
            )
        fallback_val = validate_summary_against_authorized(deterministic, payload)
        return VendorSummaryResult(
            text=deterministic,
            authorized=payload,
            validation={
                **fallback_val,
                "llm_rejected": True,
                "llm_violations": validation.get("violations") or [],
                "llm_text": llm_text,
            },
            used_llm=False,
            used_fallback=True,
            llm_rejected=True,
            propositions=propositions,
        )
    validation = validate_summary_against_authorized(deterministic, payload)
    return VendorSummaryResult(
        text=deterministic,
        authorized=payload,
        validation=validation,
        used_fallback=True,
        propositions=propositions,
    )


def _is_empty_vendor_request(state: ConversationCanonicalState) -> bool:
    from sdr.domain.vehicle_roles import customer_identity, desired_identity

    if state.signals.explicit_handoff is not True:
        return False
    facts = state.facts or {}
    if desired_identity(facts) or customer_identity(facts):
        return False
    if facts.get("desired_model") or facts.get("trade_model") or facts.get("name"):
        return False
    return True


def _empty_vendor_request_summary(state: ConversationCanonicalState) -> str:
    name = (state.customer.name or state.facts.get("name") or "").strip()
    who = f"Cliente {name}" if name and not is_placeholder_display_name(name) else "Cliente"
    return (
        f"{who} solicitou atendimento direto de um vendedor. "
        "Ainda não informou nome, veículo de interesse ou tipo de negociação."
    )


def _fmt_money(value: object) -> str | None:
    """Format a numeric money value as 'R$ 40.000'."""
    try:
        v = int(float(str(value).replace(",", ".").replace(".", ""))) if isinstance(value, str) else int(value)  # type: ignore[arg-type]
        # Re-parse properly
        v = int(float(str(value)))
        return f"R$ {v:,}".replace(",", ".")
    except (TypeError, ValueError):
        return None


def _build_vendor_summary_deterministic(state: ConversationCanonicalState) -> str:
    """Deterministic narrative summary — no LLM required."""
    facts = state.facts
    name = (state.customer.name or "").strip()
    if is_placeholder_display_name(name):
        name = facts.get("name", "")  # type: ignore[assignment]

    age = _compute_age(facts.get("birth_date"))  # type: ignore[arg-type]
    location_parts = list(filter(None, [
        str(facts.get("birth_city") or "").strip() or None,
        str(facts.get("birth_state") or "").strip() or None,
    ]))

    # Opening sentence
    intro = f"Cliente {name}" if name else "Cliente"
    if age:
        intro += f" tem {age} anos"
    if location_parts:
        intro += (", " if age else " é") + " natural de " + "/".join(location_parts)
    intro += "."

    # Minimal state: if intent is UNKNOWN and no relevant facts, report honestly.
    from sdr.domain.types import BusinessIntent
    from sdr.domain.vehicle_roles import format_vehicle_label, get_customer_vehicle, get_desired_vehicle

    if _is_empty_vendor_request(state):
        return _empty_vendor_request_summary(state)

    if state.intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK) and not facts:
        return (
            f"{intro} solicitou atendimento direto de um vendedor. "
            "Ainda não informou nome, veículo de interesse ou tipo de negociação."
        )

    # Interest
    desired = format_vehicle_label(get_desired_vehicle(facts)) or (
        facts.get("desired_vehicle_text")
        or facts.get("desired_model")
        or facts.get("vehicle_interest")
    )
    cv = get_customer_vehicle(facts)
    intent_label = {
        "purchase": "comprando",
        "purchase_financing": "comprando via financiamento",
        "trade": "comprando com troca",
        "sale": "vendendo",
        "consignment": "consignando",
        "refinancing": "refinanciando",
    }.get(state.intent.value, "buscando atendimento")

    interest_sentence = ""
    if state.intent.value in ("sale", "consignment", "refinancing"):
        own_label = format_vehicle_label(cv) or (
            cv.get("model") or facts.get("trade_model") or facts.get("sell_model")
        )
        if own_label:
            interest_sentence = f"Está {intent_label} um {own_label}."
        else:
            interest_sentence = f"Intenção: {intent_label}. Veículo do cliente não informado."
    elif desired:
        interest_sentence = f"Está {intent_label} um {desired}."
    elif state.intent.value not in ("unknown", "smalltalk"):
        interest_sentence = f"Intenção: {intent_label}. Veículo de interesse não informado."
    else:
        interest_sentence = "Solicitou falar com um vendedor. Não informou interesse específico."

    # Payment
    payment_parts: list[str] = []
    down = facts.get("down_payment")
    installment = facts.get("desired_installment")
    if down:
        money = _fmt_money(down)
        if money:
            payment_parts.append(f"entrada de {money}")
    if installment:
        money = _fmt_money(installment)
        if money:
            payment_parts.append(f"parcela até {money}/mês")
    payment_sentence = ""
    if payment_parts:
        payment_sentence = "Financiamento: " + ", ".join(payment_parts) + "."
    applies = facts.get("payment_applies_to")
    pay = str(facts.get("payment_method") or "").lower()
    if applies == "difference" and pay == "cash":
        payment_sentence = "Pretende pagar a diferença à vista."
    elif applies == "difference" and pay == "financing":
        payment_sentence = "Pretende financiar a diferença."

    # Own vehicle — only for intents that have a customer vehicle.
    own_parts: list[str] = []
    own_label = format_vehicle_label(cv)
    trade_model = cv.get("model") or facts.get("trade_model") or facts.get("sell_model")
    trade_color = cv.get("color") or facts.get("trade_color")
    mileage = cv.get("mileage") if cv.get("mileage") is not None else (facts.get("mileage") or facts.get("km"))
    if own_label:
        desc = own_label
        if trade_color and str(trade_color).lower() not in desc.lower():
            desc += f" ({trade_color})"
        if mileage:
            try:
                desc += f", {int(float(str(mileage).replace('.', '').replace(',', '.'))):,} km".replace(",", ".")
            except Exception:
                pass
        own_parts.append(desc)

    fin_status = cv.get("financing_status")
    trade_has_fin = facts.get("trade_has_financing")
    if fin_status == "financed" or trade_has_fin is True:
        inst_val = cv.get("installment_value") or facts.get("trade_installment_value")
        inst_rem = cv.get("installments_remaining") or facts.get("trade_installments_remaining")
        fin_desc = "com financiamento em aberto"
        if inst_val and inst_rem:
            v = _fmt_money(inst_val)
            fin_desc += f" de {v}/mês por mais {inst_rem} parcela(s)" if v else f" por {inst_rem} parcela(s)"
        own_parts.append(fin_desc)
    elif fin_status == "paid_off" or trade_has_fin is False:
        own_parts.append("quitado")

    trade_debts = facts.get("trade_has_debts")
    cv_status = cv.get("debt_status")
    if cv_status == "has_debts" or trade_debts is True:
        debt_type = cv.get("debt_types") or facts.get("trade_debt_type")
        if debt_type and str(debt_type).lower() not in {"sem_multas", "sem multa"}:
            own_parts.append(f"débitos pendentes ({debt_type})")
        else:
            own_parts.append("débitos pendentes")
    elif cv_status == "clear":
        own_parts.append("sem débitos")
    elif cv_status == "partial":
        own_parts.append("informou ausência de multas; demais débitos ainda não confirmados")

    trade_expectation = facts.get("trade_price_expectation")
    if trade_expectation:
        money = _fmt_money(trade_expectation)
        if money:
            own_parts.append(f"expectativa de {money}")

    own_sentence = ""
    if own_parts and state.intent.value in ("trade", "sale", "consignment", "refinancing"):
        if state.intent.value in ("sale", "consignment", "refinancing"):
            rest = own_parts[1:] if trade_model else own_parts
            if rest:
                own_sentence = "; ".join(rest) + "."
        else:
            own_sentence = f"Veículo de entrada: {'; '.join(own_parts)}."

    # Visit — only when a preference was actually discussed.
    visit_sentence = ""
    if state.visit_preferred_time:
        visit_sentence = (
            f"Preferência de visita registrada para {state.visit_preferred_time}, "
            "pendente de confirmação do vendedor."
        )
    elif state.signals.visit_intent is True:
        visit_sentence = "Cliente demonstrou interesse em visitar a loja."

    pending_sentence = ""
    if state.intent.value == "purchase":
        pending = []
        deferred_show = []
    else:
        pending = list(state.missing_fields or [])
        deferred_show = list(state.deferred_fields or [])
        if state.intent.value not in {"purchase_financing", "trade"}:
            pending = [p for p in pending if p not in {"cnh", "proof_of_residence", "proof_of_income", "documents"}]
            deferred_show = [p for p in deferred_show if p not in {"cnh", "proof_of_residence", "proof_of_income", "documents"}]
        if state.intent.value == "trade" and facts.get("payment_applies_to") != "difference":
            pending = [p for p in pending if p not in {"cnh", "proof_of_residence", "proof_of_income", "documents", "desired_installment"}]
            deferred_show = [p for p in deferred_show if p not in {"cnh", "proof_of_residence", "proof_of_income", "documents"}]
    if pending:
        pending_sentence = "Ainda pendente: " + ", ".join(pending) + "."
    if deferred_show:
        pending_sentence = (pending_sentence + " " if pending_sentence else "") + (
            "Adiado: " + ", ".join(deferred_show) + "."
        )

    sentences = [
        s
        for s in [intro, interest_sentence, payment_sentence, own_sentence, visit_sentence, pending_sentence]
        if s
    ]
    return " ".join(sentences)


def _vendor_summary_llm_allowed() -> bool:
    """LLM drafting is for live/replay runs, not the pytest process."""
    import os

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    from sdr.config import get_settings

    return bool((get_settings().openai_api_key or "").strip())


def _build_vendor_summary_llm(authorized: dict[str, Any]) -> str:
    """LLM-generated narrative from authorized facts only (raises on failure)."""
    import json

    import httpx

    from sdr.config import get_settings

    api_key = (get_settings().openai_api_key or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    system_prompt = (
        "Você escreve resumos de atendimento para vendedores de uma concessionária.\n"
        "Gere um parágrafo de 2-4 frases (máx. 120 palavras).\n"
        "Use SOMENTE os fatos autorizados abaixo. Não invente intenção, visita, documento ou débito.\n"
        "Se intent=sale, não mencione troca.\n"
        "Se documents_deferred não estiver vazio, diga que os documentos foram adiados — nunca que estão prontos.\n"
        "Se debt_status não for clear, não diga sem dívidas/sem débitos.\n"
        "Se visit_pending_vendor_confirm, diga preferência registrada pendente de confirmação do vendedor — "
        "nunca que a visita foi agendada.\n"
        "Se payment_applies_to=difference e method=cash, diga exatamente: pretende pagar a diferença à vista.\n"
        "Se payment_applies_to=difference e method=financing, diga exatamente: pretende financiar a diferença.\n"
        "NUNCA escreva 'pagar ou financiar' nem 'em dinheiro' para a diferença.\n"
        "Expectativa de valor do cliente NÃO é avaliação da loja — nunca diga avaliado/vale/avaliação da loja.\n"
        "Se financing_status=paid_off, NUNCA diga que o veículo está financiado.\n"
        "Se financing_status=financed, NUNCA diga que está quitado.\n"
        "Se intent=purchase, não mencione dívidas, documentos nem veículo próprio.\n"
        "Se não houver visit_preferred_time, não mencione ausência de visita.\n"
        "Se não houver nome, escreva 'O cliente'."
    )
    user_prompt = (
        "Fatos autorizados:\n"
        f"{json.dumps(authorized, ensure_ascii=False, indent=2)}"
    )

    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": get_settings().sdr_response_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 220,
        },
        timeout=8.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


_BRAND_WORDS = (
    "honda", "toyota", "ford", "fiat", "chevrolet", "hyundai", "volkswagen",
    "vw", "jeep", "peugeot", "renault", "nissan", "bmw", "mercedes",
)
_DOC_READY = re.compile(
    r"documentos?\s+\w*\s*(prontos?|recebidos?|enviados?)|"
    r"(prontos?|recebidos?|enviados?)\s+\w*\s*documentos?|"
    r"documentos necessários.{0,40}prontos",
    re.I,
)
_NO_DEBT = re.compile(r"sem\s+d[ií]vidas|sem\s+d[eé]bitos|totalmente\s+quitado e sem", re.I)
_VISIT_BOOKED = re.compile(
    r"visita\s+foi\s+agendada|agendou\s+(uma\s+)?visita|agendou\s+sua\s+visita",
    re.I,
)


def validate_summary_against_authorized(text: str, authorized: dict[str, Any]) -> dict[str, Any]:
    """Return {pass, violations}. Divergence must fail the golden scenario."""
    polar = validate_text_against_propositions(text, authorized)
    violations: list[str] = list(polar.get("violations") or [])
    low = (text or "").lower()
    intent = str(authorized.get("intent") or "")
    desired = authorized.get("desired_vehicle") if isinstance(authorized.get("desired_vehicle"), dict) else {}
    customer = authorized.get("customer_vehicle") if isinstance(authorized.get("customer_vehicle"), dict) else {}

    allowed_brands = {
        str(desired.get("brand") or "").strip().lower(),
        str(customer.get("brand") or "").strip().lower(),
    }
    allowed_brands.discard("")
    for brand in _BRAND_WORDS:
        if brand in low and brand not in allowed_brands and brand not in {
            str(desired.get("model") or "").lower(),
            str(customer.get("model") or "").lower(),
        }:
            model_ok = False
            for model in filter(None, (desired.get("model"), customer.get("model"))):
                from sdr.domain.vehicle_catalog import lookup_brand_for_model

                expected = lookup_brand_for_model(str(model))
                if expected and expected.lower() == brand:
                    model_ok = True
            if not model_ok and brand not in allowed_brands:
                violations.append(f"unauthorized_brand:{brand}")

    d_brand, d_model = desired.get("brand"), desired.get("model")
    if d_brand and d_model and not brands_compatible(str(d_brand), str(d_model)):
        violations.append("incompatible_desired_brand_model")
    if d_brand and d_model:
        if "honda" in low and "corolla" in low and str(d_model).lower() == "corolla" and str(d_brand).lower() != "honda":
            violations.append("summary_honda_corolla_mismatch")

    d_color = str(desired.get("color") or "").lower()
    c_color = str(customer.get("color") or "").lower()
    for color in ("prata", "preto", "branco", "vermelho", "cinza", "azul"):
        if color in low and color not in {d_color, c_color} and color not in str(desired.get("model") or "").lower():
            if intent in {"purchase", "purchase_financing"} and not c_color:
                violations.append(f"unauthorized_color:{color}")

    executed = list(polar.get("invariants_executed") or []) + [
        "authorized_brands",
        "compatible_desired",
        "authorized_colors",
    ]
    return {
        "pass": not violations,
        "violations": violations,
        "claims": polar.get("claims") or [],
        "propositions": polar.get("propositions") or [],
        "invariants_executed": executed,
    }
