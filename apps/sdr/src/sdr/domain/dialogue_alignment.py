"""Align the next scripted customer turn with Júlia's last question."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

ALLOWED_RESPONSE_MODES = frozenset({
    "voluntary_fact",
    "intent_change",
    "vendor_request",
    "objection",
    "vehicle_choice",
    "quoted_selection",
})

_PACKED_VEHICLE_FIELDS = frozenset({
    "trade_model",
    "trade_year",
    "trade_color",
    "mileage",
})


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in raw if not unicodedata.combining(ch))


def _quoted_vehicle_selection(spec: dict[str, Any]) -> bool:
    """Quoted listing/image reply is a valid next turn, not a skipped payment answer."""
    if spec.get("quoted_message_id") or spec.get("quoted"):
        return True
    events = spec.get("events")
    if not isinstance(events, list):
        return False
    for event in events:
        if isinstance(event, dict) and (event.get("quoted_message_id") or event.get("quoted")):
            return True
    return False


def classify_inbound_response_type(text: str) -> str | None:
    """Best-effort type of a customer utterance (not a brand/model list)."""
    folded = _fold(text)
    raw = text or ""
    if re.search(r"\bme chamo\b|\bmeu nome\b|^sou [A-ZÁÉÍÓÚÃÕ]", raw, re.I):
        return "name"
    if re.search(r"deixar (o carro |o veiculo |na loja)|aceito deixar|consign", folded):
        return "leave_at_store"
    if re.search(
        r"horario|pode ser|primeiro horario|segundo horario|"
        r"segunda|terca|quarta|quinta|sexta|sabado|\d{1,2}h|\d{1,2}:\d{2}",
        folded,
    ):
        return "visit"
    if re.search(r"documentos?|cnh|comprovante|holerite|enviar.{0,20}depois", folded):
        return "documents"
    if re.search(r"parcela desejada|ate \d+ de parcela|parcela de", folded) and "atual" not in folded:
        return "desired_installment"
    if re.search(r"diferenc|a vista|financio|financiar a", folded):
        return "payment_method"
    if re.search(r"entrada", folded):
        return "down_payment"
    if re.search(r"preciso de|uns \d+ mil|levantar", folded) and "espero" not in folded:
        return "amount_needed"
    if re.search(r"espero|expectativa de valor", folded):
        return "trade_price_expectation"
    if re.search(r"debito|multa|ipva|licenciamento|tudo em dia|em dia", folded):
        return "trade_has_debts"
    if re.search(r"quitado|financiado|financiamento em aberto", folded):
        return "trade_has_financing"
    if re.search(r"parcela atual|por mes|\/mes", folded):
        return "trade_installment_value"
    if re.search(r"\d+\s+parcelas", folded):
        return "trade_installments_remaining"
    if re.search(r"\b(19|20)\d{2}\b", folded) or re.search(r"\bkm\b", folded):
        return "trade_year"
    if re.search(r"quero (comprar|vender|trocar|consignar|refinanciar)|gostaria de", folded):
        return "intent"
    return None


def inbound_answers_field(text: str, field: str | None) -> bool:
    """Whether this customer line can count as an answer to the asked field."""
    if not field:
        return True
    folded = _fold(text)
    raw = text or ""
    if field == "name":
        return bool(
            re.search(r"\bme chamo\b|\bmeu nome\b", folded)
            or re.search(r"^sou\s+[A-ZÁÉÍÓÚÃÕa-záéíóúãõ]", raw)
            or (
                len(raw.split()) <= 6
                and re.search(r"[A-ZÁÉÍÓÚ][a-záéíóú]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóú]+)+", raw)
                and not re.search(r"\d", raw)
            )
        )
    if field == "leave_at_store":
        return bool(re.search(r"deixar|aceito|loja|sim|consign", folded))
    if field == "visit":
        return bool(
            re.search(
                r"horario|pode ser|primeiro|segundo|semana|"
                r"segunda|terca|quarta|quinta|sexta|sabado|\d{1,2}h|\d{1,2}:\d{2}|as \d",
                folded,
            )
        )
    if field == "documents":
        return bool(re.search(r"documento|cnh|comprovante|holerite|depois|enviar|mandar|nao tenho", folded))
    if field == "desired_installment":
        return bool(re.search(r"parcela|\d+", folded))
    if field == "down_payment":
        return bool(re.search(r"entrada|sem entrada|\d+", folded))
    if field == "payment_method":
        return bool(re.search(r"vista|financ|diferenc|pix|dinheiro", folded))
    if field == "amount_needed":
        return bool(re.search(r"\d+|mil|preciso", folded))
    if field == "trade_price_expectation":
        return bool(re.search(r"espero|\d+|mil|valor", folded))
    if field == "trade_has_debts":
        return bool(re.search(r"debito|multa|ipva|licenciamento|em dia|nada pendente|sem ", folded))
    if field == "trade_has_financing":
        return bool(re.search(r"quitado|financ|sim|nao", folded))
    if field == "trade_installment_value":
        return bool(re.search(r"\d+|parcela|mes", folded))
    if field == "trade_installments_remaining":
        return bool(re.search(r"\d+|parcela", folded))
    if field in _PACKED_VEHICLE_FIELDS:
        return bool(
            re.search(r"\b(19|20)\d{2}\b", folded)
            or re.search(r"\bkm\b|preto|branco|prata|cinza|vermelho|azul|civic|corolla|peugeot|compass", folded)
            or len(folded.split()) >= 2
        )
    if field == "desired_model":
        return True
    if field == "intent":
        return bool(re.search(r"comprar|vender|trocar|consign|refinanc", folded))
    return False


def evaluate_dialogue_alignment(
    *,
    expected_question_field: str | None,
    detected_question_field: str | None,
    inbound: str,
    turn_def: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check the upcoming customer line against Júlia's last question."""
    spec = turn_def or {}
    mode = str(spec.get("response_mode") or "").strip()
    tagged = spec.get("responds_to_field")
    asked = detected_question_field or expected_question_field
    inbound_type = classify_inbound_response_type(inbound)
    if tagged:
        inbound_type = str(tagged)

    if mode in ALLOWED_RESPONSE_MODES:
        aligned = True
        reason = f"response_mode:{mode}"
    elif _quoted_vehicle_selection(spec):
        aligned = True
        reason = "quoted_vehicle_selection"
        inbound_type = inbound_type or "vehicle_choice"
    elif not asked:
        aligned = True
        reason = "no_pending_question"
    elif tagged:
        aligned = str(tagged) == str(asked) or (
            str(tagged) in _PACKED_VEHICLE_FIELDS and asked in _PACKED_VEHICLE_FIELDS
        )
        reason = "responds_to_field"
        if not aligned and inbound_answers_field(inbound, asked):
            # Tagged for a packed sibling that still answers the asked field.
            aligned = True
            reason = "answers_asked_field"
    else:
        aligned = inbound_answers_field(inbound, asked)
        reason = "inferred"

    return {
        "expected_question_field": expected_question_field,
        "detected_question_field": detected_question_field,
        "next_customer_response_type": inbound_type or tagged or (asked if aligned else inbound_type),
        "dialogue_alignment": aligned,
        "response_mode": mode or None,
        "responds_to_field": tagged,
        "reason": reason,
    }
