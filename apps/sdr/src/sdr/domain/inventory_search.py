"""InventorySearchRequest — effective criteria from preference + authorized scope.

Original preference (desired_model / brand / …) is NEVER deleted by omission.
Scope widens *how* we search, not what the customer originally wanted.

Match ranking (PUBLISHED only):
  1. structured model + persisted engine exact
  2. title fallback with model + engine tokens (recovery only; does not confirm engine)
  3. structured model + unknown engine
  4. title fallback with model only
  5. same model with explicitly different persisted engine (alternative only)
  6. other alternatives
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sdr.domain.budget_status import BudgetStatus
from sdr.domain.engine_displacement import as_engine_list, format_engine_token
from sdr.domain.pending_interaction import AlternativeScope

# UI / placeholder tokens that must never be treated as real vehicle models.
# Observed in catalog when import took a first-token from a bad title/caption.
SUSPICIOUS_MODEL_TOKENS: frozenset[str] = frozenset(
    {
        "view",
        "click",
        "edit",
        "null",
        "undefined",
        "none",
        "n/a",
        "na",
        "test",
        "string",
        "não informado",
        "nao informado",
    }
)


def normalize_search_token(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    # Strip invisible / bidi marks (e.g. U+200E in catalog "‎View").
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def is_suspicious_model(model: str | None) -> bool:
    token = normalize_search_token(model)
    if not token:
        return True
    if token in SUSPICIOUS_MODEL_TOKENS:
        return True
    # Extremely short non-alphanumeric junk.
    if len(token) <= 2 and not token.isalnum():
        return True
    return False


@dataclass(slots=True)
class InventorySearchRequest:
    """Effective inventory query for one Decision cycle."""

    original_model: str | None = None
    original_brand: str | None = None
    original_vehicle_text: str | None = None
    category: str | None = None
    vehicle_type: str | None = None
    alternative_scope: AlternativeScope = AlternativeScope.NONE
    budget: float | None = None
    budget_status: BudgetStatus = BudgetStatus.UNKNOWN
    # Query tokens used for model/title matching (from original preference).
    query_tokens: list[str] = field(default_factory=list)
    # When True, apply priceCash upper bound from budget.
    apply_budget_filter: bool = False
    limit: int = 3
    # Canonical displacement preference — never re-parsed from free text at search time.
    engine_displacement_liters: list[Decimal] = field(default_factory=list)
    engine_flexible: bool = False
    engine_any: bool = False

    def as_trace_dict(self) -> dict[str, Any]:
        return {
            "original_model": self.original_model,
            "original_brand": self.original_brand,
            "original_vehicle_text": self.original_vehicle_text,
            "category": self.category,
            "vehicle_type": self.vehicle_type,
            "alternative_scope": self.alternative_scope.value,
            "budget": self.budget,
            "budget_status": self.budget_status.value,
            "query_tokens": self.query_tokens,
            "apply_budget_filter": self.apply_budget_filter,
            "limit": self.limit,
            "engine_displacement_liters": [
                format_engine_token(v) for v in self.engine_displacement_liters
            ],
            "engine_flexible": self.engine_flexible,
            "engine_any": self.engine_any,
        }


def _primary_query_text(facts: dict[str, Any]) -> str | None:
    for key in (
        "desired_model",
        "desired_vehicle_text",
        "desired_vehicle",
        "vehicle_interest",
        "model",
        "category",
    ):
        value = facts.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def build_inventory_search_request(
    facts: dict[str, Any],
    *,
    alternative_scope: AlternativeScope = AlternativeScope.NONE,
    budget_status: BudgetStatus = BudgetStatus.UNKNOWN,
    limit: int = 3,
) -> InventorySearchRequest:
    """Build search request from canonical facts + authorized scope."""
    model = facts.get("desired_model")
    if not isinstance(model, str) or not model.strip():
        model = None
    else:
        model = model.strip()

    brand = facts.get("brand") or facts.get("desired_brand")
    if not isinstance(brand, str) or not brand.strip():
        brand = None
    else:
        brand = brand.strip()

    vehicle_text = facts.get("desired_vehicle_text")
    if not isinstance(vehicle_text, str) or not vehicle_text.strip():
        vehicle_text = None
    else:
        vehicle_text = vehicle_text.strip()

    category = facts.get("category")
    if not isinstance(category, str) or not category.strip():
        category = None
    else:
        category = category.strip()

    vehicle_type = facts.get("vehicle_type") or facts.get("type")
    if not isinstance(vehicle_type, str) or not vehicle_type.strip():
        vehicle_type = None
    else:
        vehicle_type = vehicle_type.strip().upper()

    # ANY_VEHICLE: customer widened to any car — prefer CAR type when no type set.
    if alternative_scope == AlternativeScope.ANY_VEHICLE and vehicle_type is None:
        # Infer soft preference for cars when language said "carro"; leave None
        # when category already encodes something else.
        if category and normalize_search_token(category) in {"moto", "motorcycle", "scooter"}:
            vehicle_type = None
        else:
            vehicle_type = "CAR"

    budget_raw = facts.get("budget") if facts.get("budget") is not None else facts.get("max_price")
    budget: float | None
    try:
        budget = float(budget_raw) if budget_raw is not None else None
    except (TypeError, ValueError):
        budget = None

    apply_budget = budget_status == BudgetStatus.PROVIDED and budget is not None

    engines = as_engine_list(facts.get("desired_engine_displacement_liters"))
    engine_flexible = facts.get("desired_engine_flexible") is True
    engine_any = facts.get("desired_engine_any") is True
    if engine_any:
        engines = []

    primary = _primary_query_text(facts)
    tokens: list[str] = []
    if primary:
        tokens.append(normalize_search_token(primary))
    if brand:
        tokens.append(normalize_search_token(brand))
    # Dedupe preserving order.
    seen: set[str] = set()
    query_tokens: list[str] = []
    for t in tokens:
        if t and t not in seen:
            seen.add(t)
            query_tokens.append(t)

    return InventorySearchRequest(
        original_model=model,
        original_brand=brand,
        original_vehicle_text=vehicle_text,
        category=category,
        vehicle_type=vehicle_type,
        alternative_scope=alternative_scope,
        budget=budget,
        budget_status=budget_status,
        query_tokens=query_tokens,
        apply_budget_filter=apply_budget,
        limit=limit,
        engine_displacement_liters=engines,
        engine_flexible=engine_flexible,
        engine_any=engine_any,
    )


def inventory_search_key_from_request(req: InventorySearchRequest) -> str:
    """Stable hash of *effective* search criteria (includes scope + budget status)."""
    payload = {
        "original_model": req.original_model,
        "original_brand": req.original_brand,
        "original_vehicle_text": req.original_vehicle_text,
        "category": req.category,
        "vehicle_type": req.vehicle_type,
        "alternative_scope": req.alternative_scope.value,
        "budget": req.budget if req.apply_budget_filter else None,
        "budget_status": req.budget_status.value,
        "apply_budget_filter": req.apply_budget_filter,
        "engine_displacement_liters": [
            format_engine_token(v) for v in req.engine_displacement_liters
        ]
        or None,
        "engine_flexible": req.engine_flexible,
        "engine_any": req.engine_any,
    }
    return hashlib.md5(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:8]


def inventory_search_key(
    facts: dict[str, Any],
    *,
    alternative_scope: AlternativeScope = AlternativeScope.NONE,
    budget_status: BudgetStatus = BudgetStatus.UNKNOWN,
) -> str:
    """Hash search criteria — prefer this over hashing raw facts alone."""
    req = build_inventory_search_request(
        facts,
        alternative_scope=alternative_scope,
        budget_status=budget_status,
    )
    return inventory_search_key_from_request(req)
