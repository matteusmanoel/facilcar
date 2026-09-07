"""Classify an outbound question into a canonical ask_field.

Used to reject Composer output that answers a different roteiro field
than Decision requested. Keyword clusters, not per-copy regex lists.
"""

from __future__ import annotations

import unicodedata
from typing import Any

# Canonical field → distinctive tokens. First match by score wins.
_FIELD_SIGNALS: dict[str, tuple[str, ...]] = {
    "trade_has_debts": (
        "debito",
        "multa",
        "ipva",
        "licenciamento",
        "patente",
        "pendencia no veiculo",
        "em dia",
    ),
    "trade_price_expectation": (
        "expectativa de valor",
        "valor que voce tem em mente",
        "valor que voce tem",
        "quanto pretende no",
        "quanto espera pelo",
        "valor para o seu",
        "valor do seu",
    ),
    "name": (
        "seu nome",
        "tu nombre",
        "me diga seu nome",
        "me dices tu nombre",
    ),
    "desired_installment": (
        "parcela",
        "cuota",
        "valor de parcela",
    ),
    "documents": (
        "cnh",
        "comprovante",
        "holerite",
        "documentos",
        "licencia",
    ),
    "down_payment": (
        "entrada",
        "entrada ou",
        "cuanto dar de entrada",
    ),
    "payment_method": (
        "a vista ou financiado",
        "vista ou financiado",
        "contado o financiado",
    ),
    "trade_has_financing": (
        "financiamento em aberto",
        "financiamiento vigente",
        "ainda esta financiado",
        "tem financiamento",
    ),
    "trade_installment_value": (
        "valor atual da parcela",
        "valor de la cuota actual",
        "parcela atual",
    ),
    "trade_installments_remaining": (
        "parcelas ainda restam",
        "cuotas quedan",
        "quantas parcelas",
    ),
    "trade_year": ("ano", "de que ano", "qual o ano"),
    "trade_color": ("cor", "color"),
    "mileage": ("km", "quilometr", "rodados"),
    "trade_model": ("marca e modelo", "marca, modelo", "qual marca"),
    "desired_model": (
        "voce esta buscando",
        "esta procurando",
        "modelo ou tipo",
    ),
    "amount_needed": (
        "levantar",
        "refinanciamento",
        "precisa levantar",
    ),
    "leave_at_store": (
        "deixar o carro na loja",
        "consignacao",
        "dejar el auto",
    ),
    "visit": (
        "horario",
        "segunda",
        "terca",
        "quarta",
        "quinta",
        "sexta",
        "sabado",
        "as ",
        "h?",
    ),
    "deal_type": ("compra ou troca", "compra o permuta"),
    "intent": (
        "comprar, vender",
        "trocar, consignar",
        "refinanciar",
    ),
}


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in raw if not unicodedata.combining(ch))


def extract_question_text(bubbles: list[str] | None) -> str:
    texts = [str(b) for b in (bubbles or []) if b]
    interrogatives = [b for b in texts if "?" in b]
    if interrogatives:
        return interrogatives[-1]
    return texts[-1] if texts else ""


def classify_question_field(question: str) -> str | None:
    """Return the canonical field the question is about, or None."""
    folded = _fold(question)
    if not folded.strip():
        return None
    scores: dict[str, int] = {}
    for field, tokens in _FIELD_SIGNALS.items():
        score = 0
        for token in tokens:
            if _fold(token) in folded:
                score += 1 + (2 if len(token) > 12 else 0)
        if score:
            scores[field] = score
    if not scores:
        return None
    # Debts vs expectation: explicit expectation phrasing wins over a lone "valor".
    if "expectativa" in folded or "tem em mente para o seu" in folded or "tem em mente para tu" in folded:
        scores["trade_price_expectation"] = scores.get("trade_price_expectation", 0) + 5
        scores.pop("trade_has_debts", None)
    if any(k in folded for k in ("debito", "multa", "ipva", "licenciamento")):
        scores["trade_has_debts"] = scores.get("trade_has_debts", 0) + 5
        if "expectativa" not in folded:
            scores.pop("trade_price_expectation", None)
    if "parcela" in folded and "financiamento em aberto" not in folded:
        if "valor atual da parcela" in folded:
            scores["trade_installment_value"] = scores.get("trade_installment_value", 0) + 4
        elif "entrada" in folded:
            scores["down_payment"] = scores.get("down_payment", 0) + 8
            scores.pop("desired_installment", None)
        else:
            scores["desired_installment"] = scores.get("desired_installment", 0) + 3
    if "entrada" in folded:
        scores["down_payment"] = scores.get("down_payment", 0) + 5
    return max(scores, key=scores.get)


def evaluate_adherence(
    bubbles: list[str],
    expected_field: str | None,
    *,
    action: str | None = None,
) -> dict[str, Any]:
    """Compare the outbound question with the Decision ask_field."""
    expected = (expected_field or "").strip()
    action_val = (action or "").lower()
    question = extract_question_text(bubbles)
    detected = classify_question_field(question) if question else None
    needs_question = action_val in {
        "ask_info",
        "show_offers",
        "send_photos",
        "register_visit_interest",
    } and bool(expected)
    if not needs_question:
        return {
            "expected_question_field": expected or None,
            "detected_question_field": detected,
            "outbound_question": question or None,
            "match": True,
            "skipped": True,
        }
    match = bool(detected and detected == expected)
    if not match and expected == "visit" and detected == "visit":
        match = True
    if not match and expected and detected is None and question:
        # Unclassified question against a required field is a mismatch.
        match = False
    return {
        "expected_question_field": expected,
        "detected_question_field": detected,
        "outbound_question": question or None,
        "match": match,
        "skipped": False,
    }


def replace_question_bubble(bubbles: list[str], replacement: str | None) -> list[str]:
    """Swap the last interrogative bubble for the safe template question."""
    if not replacement:
        return list(bubbles or [])
    out = list(bubbles or [])
    for idx in range(len(out) - 1, -1, -1):
        if "?" in out[idx]:
            out[idx] = replacement
            return out
    out.append(replacement)
    return out
