"""Vendor-facing CRM summary — deterministic projection of canonical state.

The admin "Resumo da Júlia" and the WhatsApp handoff confirmation share this
builder. Canonical enums and raw facts stay in metadataJson / structured tables.
"""

from __future__ import annotations

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


def build_vendor_summary(state: ConversationCanonicalState) -> str:
    """Human-readable brief for the seller (and handoff confirmation)."""
    parts: list[str] = []

    name = (state.customer.name or "").strip()
    if name and not is_placeholder_display_name(name):
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

    if state.visit_preferred_time:
        parts.append(f"Prefere visitar: {state.visit_preferred_time}")

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
