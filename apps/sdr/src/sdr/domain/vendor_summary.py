"""Vendor-facing CRM summary — deterministic projection of canonical state.

The admin "Resumo da Júlia" and the WhatsApp handoff confirmation share this
builder. Canonical enums and raw facts stay in metadataJson / structured tables.
"""

from __future__ import annotations

import re
from datetime import date

from sdr.domain.types import ConversationCanonicalState


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


def build_vendor_summary(state: ConversationCanonicalState) -> str:
    """Human-readable narrative brief for the seller (CRM and handoff confirmation).

    Prefers a narrative LLM-generated paragraph when the OpenAI client is
    available at runtime.  Falls back to a deterministic bullet-free summary
    so the system never crashes without the LLM.
    """
    # Try async-safe synchronous call if client available.
    try:
        return _build_vendor_summary_llm(state)
    except Exception:
        pass
    return _build_vendor_summary_deterministic(state)


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
    if state.intent in (BusinessIntent.UNKNOWN, BusinessIntent.SMALLTALK) and not facts:
        return f"{intro} Cliente solicitou atendimento. Não há informações sobre veículo ou intenção comercial."

    # Interest
    desired = (
        facts.get("desired_vehicle_text")
        or facts.get("desired_model")
        or facts.get("vehicle_interest")
    )
    intent_label = {
        "purchase": "comprando",
        "purchase_financing": "comprando via financiamento",
        "trade": "comprando com troca",
        "sale": "vendendo",
        "consignment": "consignando",
        "refinancing": "refinanciando",
    }.get(state.intent.value, "buscando atendimento")

    interest_sentence = ""
    if desired:
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

    # Own vehicle
    own_parts: list[str] = []
    trade_model = facts.get("trade_model") or facts.get("sell_model")
    trade_year = facts.get("trade_year") or facts.get("sell_year")
    trade_color = facts.get("trade_color")
    mileage = facts.get("mileage") or facts.get("km")
    if trade_model:
        desc = str(trade_model)
        if trade_year:
            desc += f" {trade_year}"
        if trade_color:
            desc += f" ({trade_color})"
        if mileage:
            try:
                desc += f", {int(float(str(mileage).replace('.', '').replace(',', '.'))):,} km".replace(",", ".")
            except Exception:
                pass
        own_parts.append(desc)

    trade_has_fin = facts.get("trade_has_financing")
    if trade_has_fin is True:
        inst_val = facts.get("trade_installment_value")
        inst_rem = facts.get("trade_installments_remaining")
        fin_desc = "com financiamento em aberto"
        if inst_val and inst_rem:
            v = _fmt_money(inst_val)
            fin_desc += f" de {v}/mês por mais {inst_rem} parcela(s)" if v else f" por {inst_rem} parcela(s)"
        own_parts.append(fin_desc)
    elif trade_has_fin is False:
        own_parts.append("quitado")

    trade_debts = facts.get("trade_has_debts")
    if trade_debts is True:
        debt_type = facts.get("trade_debt_type")
        own_parts.append(f"débitos pendentes ({debt_type})" if debt_type else "débitos pendentes")
    elif trade_debts is False:
        own_parts.append("sem débitos")

    trade_expectation = facts.get("trade_price_expectation")
    if trade_expectation:
        money = _fmt_money(trade_expectation)
        if money:
            own_parts.append(f"expectativa de {money}")

    own_sentence = ""
    if own_parts:
        own_sentence = f"Veículo de entrada: {'; '.join(own_parts)}."

    # Visit
    visit_sentence = ""
    if state.visit_preferred_time:
        visit_sentence = f"Prefere visitar: {state.visit_preferred_time}."

    sentences = [s for s in [intro, interest_sentence, payment_sentence, own_sentence, visit_sentence] if s]
    return " ".join(sentences)


def _build_vendor_summary_llm(state: ConversationCanonicalState) -> str:
    """LLM-generated narrative paragraph for CRM (sync wrapper, raises on failure)."""
    import json

    import httpx

    from sdr.config import get_settings

    api_key = (get_settings().openai_api_key or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    facts_clean = {k: v for k, v in state.facts.items() if v is not None}
    payload = {
        "customer_name": state.customer.name or facts_clean.get("name"),
        "intent": state.intent.value,
        "facts": facts_clean,
        "visit_preferred_time": state.visit_preferred_time,
    }

    system_prompt = (
        "Você é um assistente que escreve resumos de atendimento para uma concessionária.\n"
        "Gere um parágrafo dissertativo de 2-4 frases (máx. 120 palavras) resumindo o atendimento.\n"
        "Escreva como 'Cliente [nome]...' — sem tópicos, sem listas, sem markdown.\n"
        "Use somente fatos presentes no estado — nunca invente dados.\n"
        "Se não houver nome, escreva 'O cliente'."
    )
    user_prompt = f"Estado do atendimento:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"

    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 200,
        },
        timeout=8.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()
