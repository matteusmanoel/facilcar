"""Inventory tool — PUBLISHED vehicles only (Prisma ``facilcar.Vehicle``).

Rules (product_rules / ADR inventory):
- Only ``status = 'PUBLISHED'`` is available stock.
- ``priceCash`` is the primary price.
- Never invent mileage/color/etc. — null DB values stay unavailable.
- Alternatives: at most 3, ranked by abs(price−budget), then type, then brand.

Match ranking for preference search:
1. structured model + persisted engine exact
2. title fallback with model + engine tokens (recovery; does not confirm engine)
3. structured model + unknown engine
4. title fallback with model only
5. same model with explicitly different persisted engine (alternative only)
6. broader alternatives
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import IntEnum
from typing import Any

import asyncpg

from sdr.domain.engine_displacement import format_engine_token
from sdr.domain.inventory_search import (
    InventorySearchRequest,
    is_suspicious_model,
    normalize_search_token,
)
from sdr.domain.pending_interaction import AlternativeScope

logger = logging.getLogger(__name__)

SCHEMA = "facilcar"
MAX_ALTERNATIVES = 3
MISSING_FIELD_LABEL = "não consta no anúncio"
ENGINE_UNINFORMED_LABEL = "não informado"
# Prisma VehicleType. Propulsion/transmission tokens must never filter this column.
_PUBLISHED_VEHICLE_TYPES = frozenset({"CAR", "MOTORCYCLE", "UTILITY", "OTHER"})


class MatchTier(IntEnum):
    STRUCTURED_MODEL_ENGINE_EXACT = 0
    TITLE_MODEL_ENGINE_EXACT = 1
    STRUCTURED_MODEL_ENGINE_UNKNOWN = 2
    TITLE_MODEL_ONLY = 3
    ENGINE_INCOMPATIBLE_ALTERNATIVE = 4
    ALTERNATIVE = 5


class EngineMatch:
    EXACT = "exact"
    UNKNOWN = "unknown"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True)
class InventoryVehicle:
    """Public stock card. Optional fields are None when absent in the listing."""

    id: str
    slug: str
    title: str
    brand_name: str
    model: str
    type: str
    price_cash: Decimal | None
    mileage: int | None
    color: str | None
    year_model: int | None
    year_manufacture: int | None
    version: str | None
    engine_displacement_liters: Decimal | None = None
    engine_match: str | None = None
    match_tier: MatchTier = MatchTier.ALTERNATIVE
    images: tuple[dict[str, Any], ...] = ()

    def field(self, name: str) -> Any:
        """Return the raw field value; ``None`` means unavailable (never fabricated)."""
        return getattr(self, name)

    def format_field(self, name: str) -> str:
        """Human label for a field; missing values become an explicit uninformed label."""
        value = self.field(name)
        if value is None:
            if name in {"engine_displacement_liters", "engineDisplacementLiters"}:
                return ENGINE_UNINFORMED_LABEL
            return MISSING_FIELD_LABEL
        if name in {"engine_displacement_liters", "engineDisplacementLiters"}:
            return format_engine_token(value if isinstance(value, Decimal) else Decimal(str(value)))
        return str(value)

    def to_dict(self) -> dict[str, Any]:
        engine = (
            float(self.engine_displacement_liters)
            if self.engine_displacement_liters is not None
            else None
        )
        return {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "brand": self.brand_name,
            "model": self.model,
            "type": self.type,
            "priceCash": float(self.price_cash) if self.price_cash is not None else None,
            "mileage": self.mileage,
            "color": self.color,
            "yearModel": self.year_model,
            "yearManufacture": self.year_manufacture,
            "version": self.version,
            "engineDisplacementLiters": engine,
            "engineMatch": self.engine_match,
            "matchTier": int(self.match_tier),
            "images": list(self.images),
            "imageCount": len(self.images),
        }


def _as_decimal(value: float | Decimal | int | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _row_to_vehicle(
    row: asyncpg.Record | dict[str, Any],
    *,
    match_tier: MatchTier = MatchTier.ALTERNATIVE,
) -> InventoryVehicle:
    get = row.get if isinstance(row, dict) else row.__getitem__
    price = get("priceCash")
    model = str(get("model") or "")
    if is_suspicious_model(model):
        logger.warning(
            "published_vehicle_suspicious_model id=%s title=%r model=%r",
            get("id"),
            get("title"),
            model,
        )
    return InventoryVehicle(
        id=str(get("id")),
        slug=str(get("slug")),
        title=str(get("title")),
        brand_name=str(get("brandName")),
        model=model,
        type=str(get("type")),
        price_cash=_as_decimal(price) if price is not None else None,
        mileage=get("mileage"),
        color=get("color"),
        year_model=get("yearModel"),
        year_manufacture=get("yearManufacture"),
        version=get("version"),
        engine_displacement_liters=_read_engine_liters(get),
        match_tier=match_tier,
        images=_read_images(get),
    )


def _read_engine_liters(get: Any) -> Decimal | None:
    try:
        raw = get("engineDisplacementLiters")
    except (KeyError, IndexError):
        return None
    return _as_decimal(raw)


def _read_images(get: Any) -> tuple[dict[str, Any], ...]:
    try:
        raw = get("images")
    except (KeyError, IndexError):
        return ()
    if raw is None:
        return ()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return ()
    if not isinstance(raw, list):
        return ()
    images: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        images.append(
            {
                "id": str(item["id"]),
                "url": str(item.get("url") or ""),
                "sortOrder": int(item.get("sortOrder") or 0),
                "isCover": bool(item.get("isCover")),
            }
        )
    return tuple(images)


def rank_alternatives(
    vehicles: list[InventoryVehicle],
    *,
    budget: float | Decimal | None = None,
    prefer_type: str | None = None,
    prefer_brand: str | None = None,
    limit: int = MAX_ALTERNATIVES,
) -> list[InventoryVehicle]:
    """Rank by match_tier, then abs(priceCash−budget), type, brand; cap at ``limit``."""
    budget_dec = _as_decimal(budget)
    prefer_brand_norm = prefer_brand.strip().lower() if prefer_brand else None
    prefer_type_norm = prefer_type.strip().upper() if prefer_type else None

    def sort_key(v: InventoryVehicle) -> tuple[int, float, int, int]:
        if budget_dec is not None:
            if v.price_cash is None:
                price_delta = float("inf")
            else:
                price_delta = abs(float(v.price_cash) - float(budget_dec))
        else:
            price_delta = 0.0
        type_rank = 0 if (prefer_type_norm and v.type.upper() == prefer_type_norm) else 1
        brand_rank = (
            0
            if (prefer_brand_norm and v.brand_name.strip().lower() == prefer_brand_norm)
            else 1
        )
        return (int(v.match_tier), price_delta, type_rank, brand_rank)

    ordered = sorted(vehicles, key=sort_key)
    cap = max(0, min(limit, MAX_ALTERNATIVES))
    return ordered[:cap]


# Candidate fetch — PUBLISHED only. Text/model matching happens in Python ranking
# so title fallback works when catalog ``model`` is corrupt.
_CANDIDATE_SQL = f'''
SELECT
  v."id",
  v."slug",
  v."title",
  v."model",
  v."version",
  v."type",
  v."priceCash",
  v."mileage",
  v."color",
  v."yearModel",
  v."yearManufacture",
  v."engineDisplacementLiters",
  b."name" AS "brandName",
  COALESCE((
    SELECT json_agg(json_build_object(
      'id', vi."id",
      'url', vi."url",
      'sortOrder', vi."sortOrder",
      'isCover', vi."isCover"
    ) ORDER BY vi."sortOrder")
    FROM "{SCHEMA}"."VehicleImage" vi
    WHERE vi."vehicleId" = v."id"
  ), '[]'::json) AS "images"
FROM "{SCHEMA}"."Vehicle" v
INNER JOIN "{SCHEMA}"."Brand" b ON b."id" = v."brandId"
WHERE v."status" = 'PUBLISHED'
  AND ($1::numeric IS NULL OR v."priceCash" >= $1)
  AND ($2::numeric IS NULL OR v."priceCash" <= $2)
  AND ($3::text IS NULL OR v."type"::text = $3)
'''

# Kept for tests that assert PUBLISHED + enum cast contracts.
_SEARCH_SQL = f'''
SELECT
  v."id",
  v."slug",
  v."title",
  v."model",
  v."version",
  v."type",
  v."priceCash",
  v."mileage",
  v."color",
  v."yearModel",
  v."yearManufacture",
  v."engineDisplacementLiters",
  b."name" AS "brandName",
  COALESCE((
    SELECT json_agg(json_build_object(
      'id', vi."id",
      'url', vi."url",
      'sortOrder', vi."sortOrder",
      'isCover', vi."isCover"
    ) ORDER BY vi."sortOrder")
    FROM "{SCHEMA}"."VehicleImage" vi
    WHERE vi."vehicleId" = v."id"
  ), '[]'::json) AS "images"
FROM "{SCHEMA}"."Vehicle" v
INNER JOIN "{SCHEMA}"."Brand" b ON b."id" = v."brandId"
WHERE v."status" = 'PUBLISHED'
  AND ($1::text IS NULL OR b."name" ILIKE $1 OR b."slug" ILIKE $1)
  AND ($2::text IS NULL OR v."model" ILIKE $2 OR v."title" ILIKE $2)
  AND ($3::numeric IS NULL OR v."priceCash" >= $3)
  AND ($4::numeric IS NULL OR v."priceCash" <= $4)
  AND ($5::text IS NULL OR v."type"::text = $5)
'''


def _token_in(haystack: str, token: str) -> bool:
    if not token:
        return False
    return token in haystack


def _title_ok(title_n: str, q: str) -> bool:
    if not _token_in(title_n, q):
        return False
    if len(q) >= 3:
        return True
    return f" {q} " in f" {title_n} " or title_n.startswith(q + " ") or title_n.endswith(" " + q)


def _title_has_engine_token(title: str, engines: list[Decimal]) -> bool:
    title_n = normalize_search_token(title)
    for engine in engines:
        token = format_engine_token(engine)
        if token in title_n or token.replace(".", ",") in title_n:
            return True
    return False


def _persisted_engine_match(
    vehicle: InventoryVehicle,
    engines: list[Decimal],
) -> str | None:
    if not engines:
        return None
    if vehicle.engine_displacement_liters is None:
        return EngineMatch.UNKNOWN
    for engine in engines:
        if vehicle.engine_displacement_liters == engine:
            return EngineMatch.EXACT
    return EngineMatch.INCOMPATIBLE


def _classify_vehicle(
    vehicle: InventoryVehicle,
    *,
    query: str,
    engines: list[Decimal],
) -> InventoryVehicle | None:
    """Return ranked vehicle or None if it is not a preference match."""
    q = normalize_search_token(query)
    if not q:
        return None
    model_n = normalize_search_token(vehicle.model)
    title_n = normalize_search_token(vehicle.title)
    structured = (not is_suspicious_model(vehicle.model)) and _token_in(model_n, q)
    title_model = _title_ok(title_n, q)
    if not structured and not title_model:
        return None

    engine_rel = _persisted_engine_match(vehicle, engines)
    title_engine = bool(engines) and _title_has_engine_token(vehicle.title, engines)

    if engines:
        if structured and engine_rel == EngineMatch.EXACT:
            tier = MatchTier.STRUCTURED_MODEL_ENGINE_EXACT
        elif (
            not structured
            and title_model
            and title_engine
            and engine_rel != EngineMatch.INCOMPATIBLE
        ):
            tier = MatchTier.TITLE_MODEL_ENGINE_EXACT
        elif structured and engine_rel == EngineMatch.UNKNOWN:
            tier = MatchTier.STRUCTURED_MODEL_ENGINE_UNKNOWN
        elif engine_rel == EngineMatch.INCOMPATIBLE and (structured or title_model):
            tier = MatchTier.ENGINE_INCOMPATIBLE_ALTERNATIVE
        elif title_model:
            tier = MatchTier.TITLE_MODEL_ONLY
        else:
            return None
    else:
        if structured:
            tier = MatchTier.STRUCTURED_MODEL_ENGINE_UNKNOWN
        else:
            tier = MatchTier.TITLE_MODEL_ONLY

    return _with_tier(vehicle, tier, engine_rel)


def _with_tier(
    v: InventoryVehicle,
    tier: MatchTier,
    engine_match: str | None = None,
) -> InventoryVehicle:
    return InventoryVehicle(
        id=v.id,
        slug=v.slug,
        title=v.title,
        brand_name=v.brand_name,
        model=v.model,
        type=v.type,
        price_cash=v.price_cash,
        mileage=v.mileage,
        color=v.color,
        year_model=v.year_model,
        year_manufacture=v.year_manufacture,
        version=v.version,
        engine_displacement_liters=v.engine_displacement_liters,
        engine_match=engine_match if engine_match is not None else v.engine_match,
        match_tier=tier,
        images=v.images,
    )


def select_ranked_vehicles(
    candidates: list[InventoryVehicle],
    req: InventorySearchRequest,
) -> list[InventoryVehicle]:
    """Apply match tiers + alternative ranking from a candidate set."""
    scope = req.alternative_scope
    primary = req.original_model or req.original_vehicle_text or req.category
    brand = req.original_brand
    engines = list(req.engine_displacement_liters)
    budget = req.budget if req.apply_budget_filter else None

    classified: list[InventoryVehicle] = []
    unmatched: list[InventoryVehicle] = []
    if primary and scope != AlternativeScope.ANY_VEHICLE:
        for raw in candidates:
            item = _classify_vehicle(raw, query=primary, engines=engines)
            if item is not None:
                classified.append(item)
            else:
                unmatched.append(raw)
    else:
        unmatched = list(candidates)

    preferred = [
        v for v in classified if v.match_tier < MatchTier.ENGINE_INCOMPATIBLE_ALTERNATIVE
    ]
    incompatible = [
        v for v in classified if v.match_tier == MatchTier.ENGINE_INCOMPATIBLE_ALTERNATIVE
    ]

    def _rank(items: list[InventoryVehicle], limit: int) -> list[InventoryVehicle]:
        return rank_alternatives(
            items,
            budget=budget,
            prefer_type=req.vehicle_type,
            prefer_brand=brand,
            limit=limit,
        )

    if preferred:
        ranked = _rank(preferred, req.limit)
        remaining = req.limit - len(ranked)
        if remaining > 0 and incompatible:
            ranked.extend(_rank(incompatible, remaining))
        remaining = req.limit - len(ranked)
        if remaining > 0 and scope in (AlternativeScope.SIMILAR, AlternativeScope.ANY_VEHICLE):
            extras = [_with_tier(v, MatchTier.ALTERNATIVE) for v in unmatched]
            ranked.extend(
                rank_alternatives(
                    extras,
                    budget=budget,
                    prefer_type=req.vehicle_type,
                    prefer_brand=brand if scope == AlternativeScope.SIMILAR else None,
                    limit=remaining,
                )
            )
        return ranked[: req.limit]

    if incompatible:
        return _rank(incompatible, req.limit)

    if scope in (AlternativeScope.SIMILAR, AlternativeScope.ANY_VEHICLE) or not primary:
        alts = [_with_tier(v, MatchTier.ALTERNATIVE) for v in candidates]
        return rank_alternatives(
            alts,
            budget=budget,
            prefer_type=req.vehicle_type,
            prefer_brand=brand if scope == AlternativeScope.SIMILAR else None,
            limit=req.limit,
        )

    return []


def sql_published_vehicle_type(value: str | None) -> str | None:
    """Only Prisma VehicleType values may filter ``Vehicle.type``.

    Facts like ``automatico`` / ``flex`` are preference tokens, not stock types.
    Applying them as SQL equality produces a false empty result.
    """
    if not value or not str(value).strip():
        return None
    token = str(value).strip().upper()
    if token in _PUBLISHED_VEHICLE_TYPES:
        return token
    return None


async def search_with_request(
    pool: asyncpg.Pool,
    req: InventorySearchRequest,
) -> list[InventoryVehicle]:
    """Search PUBLISHED stock using a typed InventorySearchRequest."""
    price_min = None
    price_max = req.budget if req.apply_budget_filter else None
    type_eq = sql_published_vehicle_type(req.vehicle_type)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            _CANDIDATE_SQL,
            _as_decimal(price_min),
            _as_decimal(price_max),
            type_eq,
        )

    candidates = [_row_to_vehicle(row) for row in rows]
    return select_ranked_vehicles(candidates, req)


async def search_published_vehicles(
    pool: asyncpg.Pool,
    *,
    brand: str | None = None,
    model: str | None = None,
    price_min: float | Decimal | None = None,
    price_max: float | Decimal | None = None,
    budget: float | Decimal | None = None,
    vehicle_type: str | None = None,
    prefer_brand: str | None = None,
    prefer_type: str | None = None,
    limit: int = MAX_ALTERNATIVES,
    request: InventorySearchRequest | None = None,
) -> list[InventoryVehicle]:
    """Query PUBLISHED stock; prefer ``request`` when provided."""
    if request is not None:
        return await search_with_request(pool, request)

    # Legacy kwargs path — resilient model OR title match via candidate + rank.
    from sdr.domain.budget_status import BudgetStatus

    facts: dict[str, Any] = {}
    if model:
        facts["desired_model"] = model
    if brand:
        facts["brand"] = brand
    if vehicle_type:
        facts["vehicle_type"] = vehicle_type
    if budget is not None:
        facts["budget"] = float(budget)
    elif price_max is not None:
        facts["budget"] = float(price_max)

    from sdr.domain.inventory_search import build_inventory_search_request

    budget_status = (
        BudgetStatus.PROVIDED
        if (budget is not None or price_max is not None)
        else BudgetStatus.UNKNOWN
    )
    req = build_inventory_search_request(
        facts,
        budget_status=budget_status,
        limit=limit,
    )
    if price_min is not None and req.apply_budget_filter:
        # Narrow via candidate SQL still uses only max; min applied post-filter.
        pass
    results = await search_with_request(pool, req)
    if price_min is not None:
        min_dec = _as_decimal(price_min)
        results = [
            v
            for v in results
            if v.price_cash is not None and min_dec is not None and v.price_cash >= min_dec
        ]
    # Re-rank with prefer_* overrides from legacy callers.
    return rank_alternatives(
        results,
        budget=budget,
        prefer_type=prefer_type or vehicle_type,
        prefer_brand=prefer_brand or brand,
        limit=limit,
    )


async def get_vehicle_by_id(
    pool: asyncpg.Pool,
    vehicle_id: str,
) -> InventoryVehicle | None:
    """Fetch a single PUBLISHED vehicle by id, or None if missing/not published."""
    sql = f'''
SELECT
  v."id",
  v."slug",
  v."title",
  v."model",
  v."version",
  v."type",
  v."priceCash",
  v."mileage",
  v."color",
  v."yearModel",
  v."yearManufacture",
  v."engineDisplacementLiters",
  b."name" AS "brandName",
  COALESCE((
    SELECT json_agg(json_build_object(
      'id', vi."id",
      'url', vi."url",
      'sortOrder', vi."sortOrder",
      'isCover', vi."isCover"
    ) ORDER BY vi."sortOrder")
    FROM "{SCHEMA}"."VehicleImage" vi
    WHERE vi."vehicleId" = v."id"
  ), '[]'::json) AS "images"
FROM "{SCHEMA}"."Vehicle" v
INNER JOIN "{SCHEMA}"."Brand" b ON b."id" = v."brandId"
WHERE v."id" = $1 AND v."status" = 'PUBLISHED'
'''
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, vehicle_id)
    if row is None:
        return None
    return _row_to_vehicle(row)
