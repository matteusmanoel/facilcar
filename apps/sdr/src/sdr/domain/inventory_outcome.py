"""Typed inventory tool outcomes and ResponseDirective claim policy.

Truth semantics
---------------
SUCCESS_FOUND   — may claim matching published vehicles were found
SUCCESS_EMPTY   — may claim no match in *current published stock*; may offer ≤3 alternatives
FAILED_RETRYABLE — must NOT claim absence; temporary consultation failure
FAILED_TERMINAL  — must NOT claim absence; safe recovery
NOT_EXECUTED     — must not imply any inventory result

The Composer decides *how* to say this. It must never decide *whether*
inventory is empty vs unavailable from an error string.
"""

from __future__ import annotations

import re
from typing import Any

from sdr.domain.types import InventoryOutcome

# Customer-facing failure category (sanitized — no infra details).
FAILURE_CATEGORY_RETRYABLE = "consultation_unavailable"
FAILURE_CATEGORY_TERMINAL = "consultation_failed"

_RETRYABLE_ERRORS = frozenset(
    {
        "no_db_pool",
        "timeout",
        "provider_error",
        "connection_error",
        "temporary_unavailable",
    }
)

# Phrases that assert confirmed stock absence (forbidden on failure outcomes).
ABSENCE_CLAIM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bn[aã]o\s+temos\b", re.I),
    re.compile(r"\bn[aã]o\s+h[aá]\s+(?:dispon[ií]vel|em\s+estoque)\b", re.I),
    re.compile(r"\bnenhum(?:a)?\s+dispon[ií]vel\b", re.I),
    re.compile(r"\bfora\s+de\s+estoque\b", re.I),
    re.compile(r"\bsem\s+(?:estoque|disponibilidade)\b", re.I),
    re.compile(r"\bn[aã]o\s+(?:encontrei|tenho)\s+.{0,40}dispon[ií]ve", re.I),
    re.compile(r"\bno\s+momento,?\s+n[aã]o\s+(?:temos|tenho|encontrei)\b", re.I),
    re.compile(r"\bnot\s+available\b", re.I),
    re.compile(r"\bno\s+(?:tenemos|hay)\b", re.I),
]

# Permanent commercial-policy claims (forbidden even on SUCCESS_EMPTY).
POLICY_CLAIM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bn[aã]o\s+trabalha(?:mos)?\s+com\b", re.I),
    re.compile(r"\bn[aã]o\s+vende(?:mos)?\s+(?:esse|este|essa|esta)\s+tipo\b", re.I),
    re.compile(r"\bnunca\s+(?:teremos|vamos\s+ter)\b", re.I),
]


def classify_inventory_error(error: str | None) -> InventoryOutcome:
    """Map infra/error codes to typed outcomes without exposing details to customers."""
    if not error:
        return InventoryOutcome.FAILED_TERMINAL
    low = error.strip().lower()
    if low in _RETRYABLE_ERRORS or "timeout" in low or "connection" in low:
        return InventoryOutcome.FAILED_RETRYABLE
    if low in {"unknown_tool", "malformed_result", "invalid_payload"}:
        return InventoryOutcome.FAILED_TERMINAL
    # Default: treat unknown failures as retryable (safer than claiming absence).
    return InventoryOutcome.FAILED_RETRYABLE


def inventory_result(
    *,
    outcome: InventoryOutcome,
    count: int = 0,
    vehicles: list[dict[str, Any]] | None = None,
    alternatives: list[dict[str, Any]] | None = None,
    search_params: dict[str, Any] | None = None,
    failure_category: str | None = None,
    retryable: bool | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    """Build a sanitized inventory ToolResult dict."""
    if retryable is None:
        retryable = outcome == InventoryOutcome.FAILED_RETRYABLE
    payload: dict[str, Any] = {
        "tool": "inventory_search",
        "outcome": outcome.value,
        "status": outcome.value,
        "count": count,
        "vehicles": vehicles or [],
        "alternatives": alternatives or [],
        "retryable": retryable,
        "search_params": search_params or {},
    }
    if failure_category:
        payload["failure_category"] = failure_category
    if error_code:
        # Internal only — never shown to customer; kept for trace/debug.
        payload["error_code"] = error_code
    # Legacy flags for gradual migration (derived from outcome — never invent).
    payload["found"] = outcome == InventoryOutcome.SUCCESS_FOUND
    if outcome in (InventoryOutcome.FAILED_RETRYABLE, InventoryOutcome.FAILED_TERMINAL):
        payload["error"] = error_code or failure_category or "inventory_failed"
    return payload


def claims_for_inventory_outcome(
    outcome: InventoryOutcome,
) -> tuple[list[str], list[str]]:
    """Return (allowed_claims, forbidden_claims) for ResponseDirective."""
    if outcome == InventoryOutcome.SUCCESS_FOUND:
        return (
            ["matching_published_vehicles_found", "list_up_to_3_offers"],
            ["no_stock", "store_does_not_sell_category", "permanent_unavailability"],
        )
    if outcome == InventoryOutcome.SUCCESS_EMPTY:
        return (
            [
                "no_matching_published_vehicle_in_current_stock",
                "offer_up_to_3_alternatives",
                "ask_if_alternatives_acceptable",
            ],
            [
                "store_does_not_work_with_category",
                "store_will_never_have_it",
                "permanent_unavailability",
            ],
        )
    if outcome == InventoryOutcome.SUCCESS_SOLD:
        return (
            [
                "vehicle_sold_or_unpublished",
                "offer_alternatives",
            ],
            [
                "vehicle_still_available",
                "store_does_not_work_with_category",
                "permanent_unavailability",
            ],
        )
    if outcome == InventoryOutcome.FAILED_RETRYABLE:
        return (
            [
                "consultation_temporarily_unavailable",
                "can_try_again",
                "can_forward_to_team",
            ],
            [
                "no_stock",
                "no_vehicle_available",
                "store_does_not_sell_category",
                "confirmed_absence",
            ],
        )
    if outcome == InventoryOutcome.FAILED_TERMINAL:
        return (
            ["consultation_failed", "safe_recovery", "can_forward_to_team"],
            [
                "no_stock",
                "no_vehicle_available",
                "store_does_not_sell_category",
                "confirmed_absence",
            ],
        )
    # NOT_EXECUTED
    return (
        [],
        ["no_stock", "no_vehicle_available", "inventory_result_implied"],
    )


def extract_inventory_outcome(tool_results: list[dict[str, Any]]) -> InventoryOutcome:
    """Read typed outcome from tool results; default NOT_EXECUTED."""
    for r in tool_results:
        if r.get("tool") != "inventory_search":
            continue
        raw = r.get("outcome") or r.get("status")
        if isinstance(raw, str):
            try:
                return InventoryOutcome(raw)
            except ValueError:
                pass
        if r.get("error"):
            return classify_inventory_error(str(r.get("error")))
        if r.get("found") and r.get("vehicles"):
            return InventoryOutcome.SUCCESS_FOUND
        if "found" in r or "count" in r:
            return InventoryOutcome.SUCCESS_EMPTY
    return InventoryOutcome.NOT_EXECUTED


def is_semantic_inventory_success(outcome: InventoryOutcome) -> bool:
    return outcome in (InventoryOutcome.SUCCESS_FOUND, InventoryOutcome.SUCCESS_EMPTY, InventoryOutcome.SUCCESS_SOLD)


def contains_absence_claim(text: str) -> bool:
    return any(p.search(text) for p in ABSENCE_CLAIM_PATTERNS)


def contains_policy_claim(text: str) -> bool:
    return any(p.search(text) for p in POLICY_CLAIM_PATTERNS)


def inventory_fallback_bubbles(outcome: InventoryOutcome, *, language: str = "pt-BR") -> list[str]:
    """Deterministic safe bubbles — Composer must not invent stock status."""
    es = language.lower().startswith("es")
    if outcome == InventoryOutcome.SUCCESS_FOUND:
        if es:
            return ["Encontré opciones en el stock publicado. ¿Quieres que te detalle alguna?"]
        return ["Encontrei opções no estoque publicado. Quer que eu detalhe alguma?"]
    if outcome == InventoryOutcome.SUCCESS_EMPTY:
        if es:
            return [
                "No encontré una opción con ese perfil en el stock actual.",
                "¿Quieres que te muestre alternativas parecidas, si hubiera?",
            ]
        return [
            "Não encontrei uma opção com esse perfil no estoque atual.",
            "Quer que eu veja alternativas parecidas, se tiver?",
        ]
    if outcome == InventoryOutcome.SUCCESS_SOLD:
        if es:
            return [
                "Ese vehículo ya fue vendido.",
                "¿Hay algún otro modelo que te interese?",
            ]
        return [
            "Esse veículo já foi vendido.",
            "Quais outros modelos você está procurando?",
        ]
    if outcome == InventoryOutcome.FAILED_RETRYABLE:
        if es:
            return [
                "No pude consultar nuestro stock ahora.",
                "Puedo intentar de nuevo o encaminar tu interés al equipo.",
            ]
        return [
            "Não consegui consultar nosso estoque agora.",
            "Posso tentar novamente ou encaminhar seu interesse para a equipe.",
        ]
    if outcome == InventoryOutcome.FAILED_TERMINAL:
        if es:
            return [
                "Tuve un problema al consultar el stock.",
                "Puedo encaminar tu interés al equipo para continuar.",
            ]
        return [
            "Tive um problema ao consultar o estoque.",
            "Posso encaminhar seu interesse para a equipe continuar com você.",
        ]
    return []
