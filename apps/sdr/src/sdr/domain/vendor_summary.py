"""Vendor-facing CRM summary — deterministic projection of canonical state.

The admin "Resumo da Júlia" and the WhatsApp handoff confirmation share this
builder. Canonical enums and raw facts stay in metadataJson / structured tables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sdr.domain.age import compute_age
from sdr.domain.authorized_facts import build_authorized_facts
from sdr.domain.summary_labels import (
    as_int,
    docs_deferred_sentence,
    docs_pending_sentence,
    docs_received_sentence,
    format_km,
    format_money,
    join_pt,
    parcelas_label,
)
from sdr.domain.summary_propositions import (
    build_propositions,
    validate_text_against_propositions,
)
from sdr.domain.age import compute_age
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
    return compute_age(birth_date_str)


ORIGIN_DETERMINISTIC = "deterministic"
ORIGIN_SPECIAL_VENDOR_REQUEST = "deterministic_special_vendor_request"
ORIGIN_LLM = "llm"
ORIGIN_DETERMINISTIC_AFTER_LLM_REJECT = "deterministic_after_llm_reject"


@dataclass
class VendorSummaryResult:
    text: str
    authorized: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    used_llm: bool = False
    used_fallback: bool = False
    llm_rejected: bool = False
    llm_attempted: bool = False
    empty_claims_rejected: bool = False
    origin: str = ORIGIN_DETERMINISTIC
    propositions: list[dict[str, Any]] = field(default_factory=list)


def build_vendor_summary(state: ConversationCanonicalState) -> str:
    """Human-readable narrative brief for the seller (CRM and handoff confirmation)."""
    return compose_vendor_summary(state).text


def _annotate_validation(
    validation: dict[str, Any],
    *,
    origin: str,
    claim_policy: str,
) -> dict[str, Any]:
    out = dict(validation or {})
    out["summary_origin"] = origin
    out["summary_kind"] = origin
    out["claim_policy"] = claim_policy
    return out


CLAIM_POLICY_COMMERCIAL = "commercial_claims_required"
CLAIM_POLICY_VENDOR_REQUEST = "commercial_claims_not_applicable"


def compose_vendor_summary(state: ConversationCanonicalState) -> VendorSummaryResult:
    auth = build_authorized_facts(state)
    payload = auth.as_dict()
    propositions = [p.as_dict() for p in build_propositions(payload)]
    deterministic = _build_vendor_summary_deterministic(state)
    if _is_empty_vendor_request(state):
        text = _empty_vendor_request_summary(state)
        origin = ORIGIN_SPECIAL_VENDOR_REQUEST
        raw = validate_summary_against_authorized(text, payload)
        violations = [
            v
            for v in (raw.get("violations") or [])
            if v != "factual_summary_without_extracted_claims"
        ]
        raw["violations"] = violations
        raw["pass"] = not violations
        validation = _annotate_validation(
            raw,
            origin=origin,
            claim_policy=CLAIM_POLICY_VENDOR_REQUEST,
        )
        return VendorSummaryResult(
            text=text,
            authorized=payload,
            validation=validation,
            used_fallback=False,
            origin=origin,
            propositions=propositions,
        )
    llm_text = None
    llm_attempted = False
    if _vendor_summary_llm_allowed():
        llm_attempted = True
        try:
            llm_text = _build_vendor_summary_llm(payload)
        except Exception:
            llm_text = None
    if llm_text:
        validation = validate_summary_against_authorized(llm_text, payload)
        empty_claims = "factual_summary_without_extracted_claims" in (
            validation.get("violations") or []
        )
        if validation.get("pass"):
            origin = ORIGIN_LLM
            return VendorSummaryResult(
                text=llm_text,
                authorized=payload,
                validation=_annotate_validation(
                    validation, origin=origin, claim_policy=CLAIM_POLICY_COMMERCIAL
                ),
                used_llm=True,
                llm_attempted=True,
                origin=origin,
                propositions=propositions,
            )
        origin = ORIGIN_DETERMINISTIC_AFTER_LLM_REJECT
        fallback_val = validate_summary_against_authorized(deterministic, payload)
        return VendorSummaryResult(
            text=deterministic,
            authorized=payload,
            validation=_annotate_validation(
                {
                    **fallback_val,
                    "llm_rejected": True,
                    "llm_violations": validation.get("violations") or [],
                    "llm_text": llm_text,
                    "llm_claims": validation.get("claims") or [],
                },
                origin=origin,
                claim_policy=CLAIM_POLICY_COMMERCIAL,
            ),
            used_llm=False,
            used_fallback=True,
            llm_rejected=True,
            llm_attempted=True,
            empty_claims_rejected=empty_claims,
            origin=origin,
            propositions=propositions,
        )
    origin = ORIGIN_DETERMINISTIC
    validation = validate_summary_against_authorized(deterministic, payload)
    return VendorSummaryResult(
        text=deterministic,
        authorized=payload,
        validation=_annotate_validation(
            validation, origin=origin, claim_policy=CLAIM_POLICY_COMMERCIAL
        ),
        used_fallback=False,
        llm_attempted=llm_attempted,
        origin=origin,
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


def _own_vehicle_phrase(customer: dict[str, Any]) -> str:
    from sdr.domain.vehicle_roles import format_vehicle_label

    label = format_vehicle_label(customer) or ""
    color = str(customer.get("color") or "").strip()
    if color and color.lower() not in label.lower():
        label = f"{label} {color}".strip()
    km = format_km(customer.get("mileage"))
    if km:
        label = f"{label}, com {km}" if label else f"com {km}"
    return label


def _display_who(name: str | None, age: int | None) -> str:
    if not name:
        return "O cliente"
    display = name
    if display.isupper() and len(display) > 1:
        display = display.title()
    if age is not None:
        first = display.split()[0]
        return f"{first}, {age} anos,"
    return display


def _handoff_reason_clause(reason: str | None) -> str | None:
    text = (reason or "").strip()
    if not text or "_" in text:
        return None
    return text


def _build_vendor_summary_deterministic(state: ConversationCanonicalState) -> str:
    """Production Portuguese narrative from authorized facts only."""
    from sdr.domain.vehicle_roles import format_vehicle_label

    if _is_empty_vendor_request(state):
        return _empty_vendor_request_summary(state)

    auth = build_authorized_facts(state)
    facts = state.facts
    name = (auth.name or "").strip()
    who = _display_who(name, auth.age)
    intent = state.intent.value
    customer = dict(auth.customer_vehicle or {})
    desired = dict(auth.desired_vehicle or {})
    own = _own_vehicle_phrase(customer)
    wanted = format_vehicle_label(desired) or (
        facts.get("desired_vehicle_text") or facts.get("desired_model") or facts.get("vehicle_interest")
    )

    sentences: list[str] = []

    if intent == "sale":
        subject = who.rstrip(",")
        lead = f"{subject} deseja vender seu {own}" if own else f"{subject} deseja vender o veículo"
        bits: list[str] = []
        if auth.financing_status == "paid_off":
            bits.append("quitado")
        elif auth.financing_status == "financed":
            bits.append("financiado")
        if auth.debt_status == "clear":
            bits.append("sem débitos informados")
        elif auth.debt_status == "has_debts":
            bits.append("com débitos pendentes")
        if bits:
            lead = f"{lead}, {join_pt(bits)}"
        sentences.append(lead + ".")
        expect = format_money(auth.price_expectation)
        if expect:
            sentences.append(
                f"A expectativa informada é receber aproximadamente {expect} pelo veículo."
            )
    elif intent == "consignment":
        subject = who.rstrip(",")
        lead = f"{subject} deseja deixar em consignação seu {own}" if own else f"{subject} deseja consignar o veículo"
        if auth.financing_status == "paid_off":
            lead += ", quitado"
        sentences.append(lead + ".")
        expect = format_money(auth.price_expectation)
        if expect:
            sentences.append(f"A expectativa de valor informada é de aproximadamente {expect}.")
        if auth.leave_at_store is True or str(auth.leave_at_store).strip().lower() in {"true", "1", "sim"}:
            sentences.append("O cliente aceita deixar o veículo na loja para consignação.")
    elif intent == "refinancing":
        subject = who.rstrip(",")
        lead = (
            f"{subject} busca refinanciamento de seu {own}"
            if own
            else f"{subject} busca refinanciamento"
        )
        needed = format_money(auth.amount_needed)
        if needed:
            lead += f" e informou necessidade aproximada de {needed}"
        sentences.append(lead + ".")
    elif intent == "trade":
        lead = f"{who} pretende trocar"
        if own:
            lead += f" seu {own}"
        if wanted:
            lead += f", por um {wanted}" if own else f" por um {wanted}"
        sentences.append(lead + ".")
        fin_bits: list[str] = []
        if auth.financing_status == "financed":
            fin_bits.append(_financing_clause(customer))
        elif auth.financing_status == "paid_off":
            fin_bits.append("O veículo está quitado")
        if auth.debt_status == "clear":
            extra = "e sem débitos informados" if fin_bits else "O veículo está sem débitos informados"
            if fin_bits:
                fin_bits[-1] = fin_bits[-1].rstrip(".") + ", sem débitos informados"
            else:
                fin_bits.append(extra)
        elif auth.debt_status == "has_debts":
            fin_bits.append("Há débitos pendentes")
        if fin_bits:
            text = fin_bits[0]
            if not text.endswith("."):
                text += "."
            sentences.append(text[0].upper() + text[1:] if text else text)
        expect = format_money(auth.price_expectation)
        pay = str(auth.payment_method or "").lower()
        applies = auth.payment_applies_to
        pay_clause = ""
        if applies == "difference" and pay == "financing":
            pay_clause = "pretende financiar a diferença"
            inst = format_money(auth.desired_installment)
            if inst:
                pay_clause += f", com parcela desejada de {inst}"
        elif applies == "difference" and pay == "cash":
            pay_clause = "pretende pagar a diferença à vista"
        if expect and pay_clause:
            sentences.append(
                f"A expectativa informada é receber aproximadamente {expect} pelo usado. "
                f"{pay_clause[0].upper() + pay_clause[1:]}."
            )
        elif expect:
            sentences.append(
                f"A expectativa informada é receber aproximadamente {expect} pelo usado."
            )
        elif pay_clause:
            sentences.append(pay_clause[0].upper() + pay_clause[1:] + ".")
    elif intent in {"purchase", "purchase_financing"}:
        verb = "pretende comprar via financiamento" if intent == "purchase_financing" else "pretende comprar"
        if intent == "purchase_financing" and wanted and state.primary_vehicle_id:
            lead = f"{who} demonstrou interesse principal na {wanted}"
        else:
            lead = f"{who} {verb}"
            if wanted:
                lead += f" um {wanted}"
        if intent == "purchase" and str(auth.payment_method or "").lower() == "cash":
            lead += " à vista"
        sentences.append(lead + ".")
        if intent == "purchase_financing":
            down_n = as_int(auth.down_payment)
            inst = format_money(auth.desired_installment)
            if down_n == 0:
                sent = "Pretende financiar sem entrada"
                if inst:
                    sent += f", com parcela desejada de {inst}"
                sentences.append(sent + ".")
            else:
                pay_parts: list[str] = []
                down = format_money(auth.down_payment)
                if down:
                    pay_parts.append(f"entrada de {down}")
                if inst:
                    pay_parts.append(f"parcela desejada de {inst}")
                if pay_parts:
                    sentences.append("Informou " + join_pt(pay_parts) + ".")
    else:
        intro = f"Cliente {name}" if name else "Cliente"
        sentences.append(f"{intro} está buscando atendimento.")
        if wanted:
            sentences.append(f"Demonstrou interesse em um {wanted}.")

    if auth.documents_applicable:
        deferred = list(auth.documents_deferred or [])
        received = [
            k for k, v in (auth.document_status or {}).items() if v == "received"
        ]
        missing_docs = [
            f
            for f in (auth.missing_fields or [])
            if f in {"cnh", "proof_of_residence", "proof_of_income", "documents"}
            and f not in received
            and f not in deferred
        ]
        if received:
            received_sent = docs_received_sentence(received)
            if received_sent:
                sentences.append(received_sent)
        if deferred:
            deferred_sent = docs_deferred_sentence(deferred)
            if deferred_sent:
                sentences.append(deferred_sent)
        elif missing_docs:
            pending_sent = docs_pending_sentence(missing_docs)
            if pending_sent:
                sentences.append(pending_sent)

    if auth.visit_preferred_time:
        sentences.append(f"Pretende visitar a loja na {auth.visit_preferred_time}.")

    reason = _handoff_reason_clause(auth.handoff_reason)
    if reason:
        sentences.append(reason if reason.endswith(".") else reason + ".")

    return " ".join(s for s in sentences if s)


def _financing_clause(customer: dict[str, Any]) -> str:
    rem = parcelas_label(customer.get("installments_remaining"))
    inst = format_money(customer.get("installment_value"))
    if rem and inst:
        return f"O veículo está financiado, com {rem} restantes de {inst}"
    if rem:
        return f"O veículo está financiado, com {rem} restantes"
    if inst:
        return f"O veículo está financiado, com parcelas de {inst}"
    return "O veículo está financiado"


def _vendor_summary_llm_allowed() -> bool:
    """Optional style pass. Default off: persist the validated deterministic text."""
    import os

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    from sdr.config import get_settings

    settings = get_settings()
    if not bool(getattr(settings, "sdr_summary_llm", False)):
        return False
    return bool((settings.openai_api_key or "").strip())


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
        "Se intent=sale, não mencione troca nem documentos.\n"
        "Se documents_applicable=false, não mencione documentos nem ausência de documentos.\n"
        "Se documents_deferred tiver um único documento, use o verbo no singular (ficou para envio posterior).\n"
        "Se houver mais de um documento adiado, use o plural (ficaram para envio posterior). Nunca diga que estão prontos.\n"
        "Use CNH, comprovante de residência e comprovante de renda — nunca nomes internos de campo.\n"
        "Não infira gênero: nunca escreva 'Ele espera' ou 'Ela espera'. Use 'A expectativa informada é receber...'.\n"
        "Se down_payment for 0, diga que pretende financiar sem entrada — nunca 'entrada de R$ 0'.\n"
        "Se leave_at_store for true em consignação, diga que aceita deixar o veículo na loja para consignação — não reduza a 'avaliação'.\n"
        "Não escreva flags internas: perfil completo, atendimento pronto, handoff_ready, perfil precisa ser complementado.\n"
        "Se debt_status não for clear, não diga sem dívidas/sem débitos.\n"
        "Se houver preferência de visita, diga que o cliente pretende visitar na data/hora informada — "
        "nunca que a visita está marcada, agendada, confirmada ou garantida pelo vendedor.\n"
        "Se payment_applies_to=difference e method=cash, diga exatamente: pretende pagar a diferença à vista.\n"
        "Se payment_applies_to=difference e method=financing, diga exatamente: pretende financiar a diferença "
        "e inclua a parcela desejada se desired_installment existir.\n"
        "NUNCA escreva 'pagar ou financiar' nem 'em dinheiro' para a diferença. NUNCA escreva parcela(s).\n"
        "Expectativa de valor do cliente NÃO é avaliação da loja — nunca diga avaliado/vale/avaliação da loja.\n"
        "Se financing_status=paid_off, NUNCA diga que o veículo está financiado.\n"
        "Se financing_status=financed, NUNCA diga que está quitado.\n"
        "Se intent=purchase, não mencione dívidas, documentos nem veículo próprio.\n"
        "Se intent=refinancing, não mencione visita nem 'sem pendências' de documentos.\n"
        "Se não houver visit_preferred_time, não mencione visita nem ausência de visita.\n"
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
_INTERNAL_NARRATIVE = re.compile(
    r"\bhandoff_ready\b|profile_complete|perfil completo|atendimento pronto|"
    r"perfil ainda precisa ser complementado",
    re.I,
)


def validate_summary_against_authorized(text: str, authorized: dict[str, Any]) -> dict[str, Any]:
    """Return {pass, violations}. Divergence must fail the golden scenario."""
    polar = validate_text_against_propositions(text, authorized)
    violations: list[str] = list(polar.get("violations") or [])
    low = (text or "").lower()
    if _INTERNAL_NARRATIVE.search(text or ""):
        violations.append("internal_operational_flag_in_narrative")
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
        "claim_links": polar.get("claim_links") or [],
        "propositions": polar.get("propositions") or [],
        "invariants_executed": executed,
    }
