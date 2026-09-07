"""Canonical vehicle roles — desired_vehicle vs customer_vehicle.

Legacy flat keys (trade_model, vehicle_year, color, sell_model, …) are
normalized into two nested dicts immediately after Understanding. The rest of
the pipeline must read through the accessors in this module.

Intent routing
--------------
PURCHASE / PURCHASE_FINANCING → desired_vehicle
SALE / CONSIGNMENT / REFINANCING → customer_vehicle
TRADE → both (desired_model* → desired; trade_*/vehicle_*/sell_* → customer)
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from sdr.domain.types import BusinessIntent

DESIRED_VEHICLE_KEY = "desired_vehicle"
CUSTOMER_VEHICLE_KEY = "customer_vehicle"

DESIRED_ATTRS = ("brand", "model", "year", "color", "version", "text")
CUSTOMER_ATTRS = (
    "brand",
    "model",
    "year",
    "color",
    "mileage",
    "renavam",
    "ownership",
    "financing_status",
    "installment_value",
    "installments_remaining",
    "debt_status",
    "debt_types",
    "price_expectation",
)

_CUSTOMER_ONLY_INTENTS = frozenset(
    {
        BusinessIntent.SALE,
        BusinessIntent.CONSIGNMENT,
        BusinessIntent.REFINANCING,
    }
)
_DESIRED_ONLY_INTENTS = frozenset(
    {
        BusinessIntent.PURCHASE,
        BusinessIntent.PURCHASE_FINANCING,
    }
)

# Packed utterance: "Civic 2021 preto 30000 km" / "2020, prata, 50000 km"
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
_KM_RE = re.compile(
    r"\b(\d{1,3}(?:[.\s]?\d{3})+|\d{4,7})\s*(?:km|quilometr)",
    re.I,
)
_KM_BARE_RE = re.compile(r"\b(\d{4,7})\b")
_COLOR_RE = re.compile(
    r"\b(prata|preto|preta|branco|branca|cinza|vermelho|vermelha|azul|"
    r"verde|amarelo|amarela|bege|marrom|dourado|bordo|bordô|grafite)\b",
    re.I,
)


def empty_desired() -> dict[str, Any]:
    return {}


def empty_customer() -> dict[str, Any]:
    return {}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if v is not None and v != ""}
    return {}


def get_desired_vehicle(facts: dict[str, Any]) -> dict[str, Any]:
    nested = _as_dict(facts.get(DESIRED_VEHICLE_KEY))
    if nested:
        return dict(nested)
    out: dict[str, Any] = {}
    model = facts.get("desired_model") or facts.get("desired_vehicle_text")
    if model:
        out["model"] = model
        if facts.get("desired_vehicle_text"):
            out["text"] = facts.get("desired_vehicle_text")
    if facts.get("brand") and not _looks_own_brand_conflict(facts):
        out["brand"] = facts.get("brand")
    return out


def get_customer_vehicle(facts: dict[str, Any]) -> dict[str, Any]:
    nested = _as_dict(facts.get(CUSTOMER_VEHICLE_KEY))
    if nested:
        return dict(nested)
    out: dict[str, Any] = {}
    model = facts.get("trade_model") or facts.get("sell_model") or facts.get("vehicle_model")
    if model:
        out["model"] = model
    year = facts.get("trade_year") or facts.get("sell_year") or facts.get("vehicle_year")
    if year:
        out["year"] = year
    color = facts.get("trade_color")
    if color:
        out["color"] = color
    if facts.get("mileage") is not None:
        out["mileage"] = facts.get("mileage")
    return out


def _looks_own_brand_conflict(facts: dict[str, Any]) -> bool:
    """True when brand is more likely the customer's car than the desired one."""
    return bool(facts.get("trade_model") or facts.get("vehicle_model") or facts.get("sell_model"))


def _filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def customer_has(facts: dict[str, Any], *attrs: str) -> bool:
    cv = get_customer_vehicle(facts)
    return all(_filled(cv.get(a)) for a in attrs)


def desired_has(facts: dict[str, Any], *attrs: str) -> bool:
    dv = get_desired_vehicle(facts)
    return any(_filled(dv.get(a)) for a in attrs)


def desired_identity(facts: dict[str, Any]) -> bool:
    dv = get_desired_vehicle(facts)
    return _filled(dv.get("model")) or _filled(dv.get("text")) or _filled(dv.get("brand"))


def customer_identity(facts: dict[str, Any]) -> bool:
    cv = get_customer_vehicle(facts)
    has_model = _filled(cv.get("model")) or _filled(cv.get("brand"))
    has_year = _filled(cv.get("year"))
    return bool(has_model and has_year)


def _put(target: dict[str, Any], attr: str, value: Any) -> None:
    if not _filled(value):
        return
    if attr not in target or not _filled(target.get(attr)):
        target[attr] = value


def parse_packed_vehicle_attrs(text: str) -> dict[str, Any]:
    """Extract year/color/mileage from a short packed description."""
    if not text or not str(text).strip():
        return {}
    raw = str(text)
    out: dict[str, Any] = {}
    year_m = _YEAR_RE.search(raw)
    if year_m:
        out["year"] = year_m.group(1)
    color_m = _COLOR_RE.search(raw)
    if color_m:
        out["color"] = color_m.group(1).lower()
    km_m = _KM_RE.search(raw)
    if km_m:
        digits = re.sub(r"[.\s]", "", km_m.group(1))
        try:
            out["mileage"] = int(digits)
        except ValueError:
            pass
    elif not km_m:
        # "2020, prata, 50000 km" already handled; "50000 km" too.
        # Bare 4-7 digit after color/year: treat as km when 'km' present or comma list.
        if re.search(r"\bkm\b", raw, re.I):
            pass
        else:
            nums = _KM_BARE_RE.findall(raw)
            if year_m:
                nums = [n for n in nums if n != year_m.group(1)]
            if len(nums) == 1 and int(nums[0]) >= 1000:
                out["mileage"] = int(nums[0])
    return out


def canonicalize_vehicle_roles(
    facts: dict[str, Any],
    intent: BusinessIntent,
) -> dict[str, Any]:
    """Fold legacy aliases into nested desired_vehicle / customer_vehicle.

    Does not delete historical flat keys. Nested objects are the source of
    truth for Decision / Composer / CRM.
    """
    out = deepcopy(facts) if facts else {}
    desired = _as_dict(out.get(DESIRED_VEHICLE_KEY))
    customer = _as_dict(out.get(CUSTOMER_VEHICLE_KEY))

    packed_src = " ".join(
        str(v)
        for v in (
            out.get("desired_vehicle_text"),
            out.get("vehicle_model"),
            out.get("trade_model"),
            out.get("desired_model"),
        )
        if v
    )
    packed = parse_packed_vehicle_attrs(packed_src)

    def absorb_desired() -> None:
        _put(desired, "model", out.get("desired_model"))
        _put(desired, "text", out.get("desired_vehicle_text"))
        _put(desired, "brand", out.get("brand") or out.get("desired_brand"))
        _put(desired, "year", out.get("desired_year"))
        _put(desired, "color", out.get("desired_color"))

    def absorb_customer() -> None:
        _put(customer, "model", out.get("trade_model") or out.get("sell_model") or out.get("vehicle_model"))
        _put(customer, "year", out.get("trade_year") or out.get("sell_year") or out.get("vehicle_year"))
        _put(customer, "color", out.get("trade_color") or out.get("color"))
        _put(customer, "mileage", out.get("mileage") or out.get("km"))
        _put(customer, "renavam", out.get("trade_renavam"))
        if out.get("trade_has_financing") is True:
            _put(customer, "financing_status", "financed")
        elif out.get("trade_has_financing") is False:
            _put(customer, "financing_status", "paid_off")
        _put(customer, "installment_value", out.get("trade_installment_value"))
        _put(customer, "installments_remaining", out.get("trade_installments_remaining"))
        if out.get("trade_has_debts") is True:
            _put(customer, "debt_status", "has_debts")
        elif out.get("trade_has_debts") is False:
            _put(customer, "debt_status", "clear")
        _put(customer, "debt_types", out.get("trade_debt_type"))
        _put(customer, "price_expectation", out.get("trade_price_expectation") or out.get("asking_price"))
        if out.get("trade_in_owner_is_client") is True:
            _put(customer, "ownership", "client")
        elif out.get("trade_in_owner_is_client") is False:
            _put(customer, "ownership", "third_party")

    if intent in _DESIRED_ONLY_INTENTS:
        absorb_desired()
        # Purchase: year/color on the inbound usually describe the desired car.
        if not customer:
            _put(desired, "year", out.get("year") or packed.get("year"))
            _put(desired, "color", out.get("color") or packed.get("color"))
    elif intent in _CUSTOMER_ONLY_INTENTS:
        absorb_customer()
        # LLM often emits generic year/color/mileage/model for the owned car.
        _put(customer, "model", out.get("vehicle_model") or out.get("model"))
        _put(customer, "year", out.get("year") or packed.get("year"))
        _put(customer, "color", out.get("color") or packed.get("color"))
        _put(customer, "mileage", packed.get("mileage"))
        _put(customer, "brand", out.get("brand"))
        # Never copy desired_model into customer; never copy customer into desired.
    elif intent == BusinessIntent.TRADE:
        absorb_desired()
        absorb_customer()
        _put(customer, "year", out.get("year") or packed.get("year"))
        _put(customer, "color", out.get("color") or packed.get("color"))
        _put(customer, "mileage", packed.get("mileage"))
    else:
        absorb_desired()
        absorb_customer()

    if desired:
        out[DESIRED_VEHICLE_KEY] = desired
        if desired.get("model") and not out.get("desired_model"):
            out["desired_model"] = desired["model"]
    if customer:
        out[CUSTOMER_VEHICLE_KEY] = customer
        if customer.get("model") and not out.get("trade_model"):
            out["trade_model"] = customer["model"]
        if customer.get("year") and not out.get("trade_year"):
            out["trade_year"] = customer["year"]
        if customer.get("color") and not out.get("trade_color"):
            out["trade_color"] = customer["color"]
        if customer.get("mileage") is not None and out.get("mileage") is None:
            out["mileage"] = customer["mileage"]

    return out


def merge_vehicle_dicts(prev: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(prev or {})
    for key, value in (incoming or {}).items():
        if not _filled(value):
            continue
        merged[key] = value
    return merged


def format_vehicle_label(vehicle: dict[str, Any] | None) -> str | None:
    if not vehicle:
        return None
    parts = [str(vehicle[k]).strip() for k in ("brand", "model", "year") if _filled(vehicle.get(k))]
    if not parts and _filled(vehicle.get("text")):
        return str(vehicle["text"]).strip()
    return " ".join(parts) if parts else None
