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
    """Human-readable brief for the seller (and handoff confirmation)."""
    parts: list[str] = []

    name = (state.customer.name or "").strip()
    if name and not is_placeholder_display_name(name):
        age = _compute_age(state.facts.get("birth_date"))  # type: ignore[arg-type]
        birth_city = state.facts.get("birth_city")
        birth_state = state.facts.get("birth_state")
        location_str = ""
        if birth_city or birth_state:
            city_state = "/".join(filter(None, [
                str(birth_city).strip() if birth_city else None,
                str(birth_state).strip() if birth_state else None,
            ]))
            location_str = f", {city_state}"
        age_str = f", {age} anos" if age else ""
        parts.append(f"Cliente: {name}{age_str}{location_str}")
    elif name:
        parts.append(f"Cliente: {name}")

    vehicle = (
        state.facts.get("desired_vehicle_text")
        or state.facts.get("desired_model")
        or state.facts.get("vehicle_interest")
    )
    if vehicle:
        price_raw = state.facts.get("price") or state.facts.get("asking_price")
        price_str = ""
        if price_raw:
            try:
                price_str = f" (R$ {int(price_raw):,}".replace(",", ".") + ")"
            except (TypeError, ValueError):
                price_str = ""
        parts.append(f"Interesse: {vehicle}{price_str}")

    forma = _forma_comercial(state)
    if forma:
        parts.append(f"Forma: {forma}")

    down = state.facts.get("down_payment")
    if down:
        try:
            parts.append(f"Entrada: R$ {int(down):,}".replace(",", "."))
        except (TypeError, ValueError):
            pass

    installment = state.facts.get("desired_installment")
    if installment:
        try:
            parts.append(f"Parcela até: R$ {int(installment):,}".replace(",", "."))
        except (TypeError, ValueError):
            pass

    if state.visit_preferred_time:
        parts.append(f"Visita agendada: {state.visit_preferred_time}")

    if not parts:
        intent_labels = {
            "purchase": "Compra de veículo",
            "purchase_financing": "Financiamento de veículo",
            "trade": "Troca de veículo",
            "sale": "Venda de veículo",
            "consignment": "Consignação",
            "refinancing": "Refinanciamento",
        }
        parts.append(intent_labels.get(state.intent.value, "Interesse comercial"))

    return " · ".join(parts)
