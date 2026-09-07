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

from sdr.domain.debts import compute_debt_status, merge_checks, persistable_checks
from sdr.domain.types import BusinessIntent
from sdr.domain.vehicle_catalog import enrich_vehicle, model_identity

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
    "debt_checks",
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
    """Extract year/color/mileage from a short packed description.

    A 4-digit catalog model (e.g. Peugeot 2008) is not a year unless a
    second year token is present ("Peugeot 2008 2019").
    """
    if not text or not str(text).strip():
        return {}
    raw = str(text)
    out: dict[str, Any] = {}
    from sdr.domain.vehicle_catalog import lookup_brand_for_model

    years = _YEAR_RE.findall(raw)
    year_tokens = [y for y in years if not lookup_brand_for_model(y)]
    if year_tokens:
        out["year"] = year_tokens[-1]
    elif len(years) > 1:
        out["year"] = years[-1]
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
        if re.search(r"\bkm\b", raw, re.I):
            pass
        else:
            nums = _KM_BARE_RE.findall(raw)
            skip = set(years)
            nums = [n for n in nums if n not in skip]
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
        if isinstance(out.get("debt_checks"), dict):
            customer["debt_checks"] = merge_checks(customer.get("debt_checks"), out.get("debt_checks"))
        if out.get("debt_status"):
            customer["debt_status"] = out.get("debt_status")
        elif out.get("trade_has_debts") is True:
            _put(customer, "debt_status", "has_debts")
        elif out.get("trade_has_debts") is False and customer.get("debt_status") not in {
            "partial",
            "has_debts",
        }:
            _put(customer, "debt_status", "clear")
        if customer.get("debt_checks"):
            customer["debt_checks"] = persistable_checks(customer.get("debt_checks"))
            customer["debt_status"] = compute_debt_status(customer.get("debt_checks"))
        debt_types = out.get("trade_debt_type")
        if debt_types and str(debt_types).strip().lower() not in {"sem_multas", "sem multa", "sem-multas"}:
            _put(customer, "debt_types", debt_types)
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
        desired = enrich_vehicle(desired)
        out[DESIRED_VEHICLE_KEY] = desired
        if desired.get("model") and not out.get("desired_model"):
            out["desired_model"] = desired["model"]
        if desired.get("brand") and not out.get("brand"):
            out["brand"] = desired["brand"]
    if customer:
        customer = enrich_vehicle(customer)
        if customer.get("debt_checks"):
            customer["debt_checks"] = persistable_checks(customer.get("debt_checks"))
            customer["debt_status"] = compute_debt_status(customer.get("debt_checks"))
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
        if key == "debt_checks" and isinstance(value, dict):
            merged[key] = persistable_checks(
                merge_checks(
                    merged.get("debt_checks") if isinstance(merged.get("debt_checks"), dict) else None,
                    value,
                )
            )
            continue
        if key == "_provenance" and isinstance(value, dict):
            prev_p = merged.get("_provenance") if isinstance(merged.get("_provenance"), dict) else {}
            merged[key] = {**prev_p, **value}
            continue
        if not _filled(value):
            continue
        merged[key] = value
    return merged


def substitute_desired_vehicle(
    previous: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
    inbound_text: str = "",
) -> dict[str, Any]:
    """Replace desired-vehicle identity; drop listing-bound attributes."""
    prev = _as_dict(previous)
    inc = _as_dict(incoming)
    new_model = inc.get("model") or inc.get("text")
    if not new_model:
        return merge_vehicle_dicts(prev, inc)

    out: dict[str, Any] = {"model": new_model}
    provenance: dict[str, str] = {"model": "customer"}

    packed = parse_packed_vehicle_attrs(inbound_text)
    model_mentioned = model_identity(new_model) and model_identity(new_model) in model_identity(
        inbound_text
    )
    if packed.get("color") and (model_mentioned or not prev):
        out["color"] = packed["color"]
        provenance["color"] = "customer"
    elif inc.get("color") and packed.get("color"):
        out["color"] = packed["color"]
        provenance["color"] = "customer"

    if packed.get("year") and model_mentioned:
        out["year"] = packed["year"]
        provenance["year"] = "customer"

    if inc.get("brand"):
        out["brand"] = inc["brand"]
        provenance["brand"] = "customer"

    out["_provenance"] = provenance
    return enrich_vehicle(out)


def desired_identity_changed(previous: dict[str, Any] | None, incoming_model: Any) -> bool:
    prev_id = model_identity((previous or {}).get("model") or (previous or {}).get("text"))
    new_id = model_identity(incoming_model)
    if not new_id or not prev_id:
        return False
    if new_id == prev_id:
        return False
    # "Honda Civic" → "Civic" is the same identity.
    if prev_id in new_id or new_id in prev_id:
        return False
    return True


def apply_desired_vehicle_substitution(
    facts: dict[str, Any],
    previous_facts: dict[str, Any] | None,
    incoming_facts: dict[str, Any] | None,
    inbound_text: str = "",
) -> dict[str, Any]:
    """If the desired model changed this turn, replace the nested object."""
    prev = previous_facts or {}
    incoming = incoming_facts or {}
    prev_dv = _as_dict(prev.get(DESIRED_VEHICLE_KEY))
    if not prev_dv.get("model"):
        prev_dv = get_desired_vehicle(prev)

    incoming_model = None
    inc_dv = incoming.get(DESIRED_VEHICLE_KEY)
    if isinstance(inc_dv, dict) and inc_dv.get("model"):
        incoming_model = inc_dv.get("model")
    if not incoming_model:
        incoming_model = incoming.get("desired_model")
    if not incoming_model:
        current = _as_dict(facts.get(DESIRED_VEHICLE_KEY))
        incoming_model = current.get("model") or facts.get("desired_model")

    if not desired_identity_changed(prev_dv, incoming_model):
        current = enrich_vehicle(_as_dict(facts.get(DESIRED_VEHICLE_KEY)) or get_desired_vehicle(facts))
        if current:
            facts[DESIRED_VEHICLE_KEY] = current
            if current.get("model"):
                facts["desired_model"] = current["model"]
            if current.get("brand"):
                facts["brand"] = current["brand"]
        return facts

    inc_payload = inc_dv if isinstance(inc_dv, dict) else {"model": incoming_model}
    if incoming.get("desired_model") and not inc_payload.get("model"):
        inc_payload = {**inc_payload, "model": incoming["desired_model"]}
    replaced = substitute_desired_vehicle(prev_dv, inc_payload, inbound_text)
    facts[DESIRED_VEHICLE_KEY] = replaced
    if replaced.get("model"):
        facts["desired_model"] = replaced["model"]
    if replaced.get("brand"):
        facts["brand"] = replaced["brand"]
    else:
        from sdr.domain.vehicle_catalog import brands_compatible

        if facts.get("brand") and not brands_compatible(
            str(facts.get("brand")), str(replaced.get("model"))
        ):
            facts.pop("brand", None)
    # Flat listing-bound attrs must not re-infect the new nested object.
    if not replaced.get("color"):
        facts.pop("color", None)
        facts.pop("desired_color", None)
    else:
        facts["color"] = replaced["color"]
    if not replaced.get("year"):
        facts.pop("year", None)
        facts.pop("desired_year", None)
    else:
        facts["year"] = replaced["year"]
    for listing_key in ("listing_id", "inventory_id", "ad_id", "vehicle_id"):
        facts.pop(listing_key, None)
    return facts


def format_vehicle_label(vehicle: dict[str, Any] | None) -> str | None:
    """Single presentation helper — never duplicate brand/model/year tokens."""
    if not vehicle:
        return None
    brand = str(vehicle.get("brand") or "").strip()
    model = str(vehicle.get("model") or "").strip()
    year = str(vehicle.get("year") or "").strip()
    if brand and model:
        model_l = model.lower()
        brand_l = brand.lower()
        if model_l == brand_l or model_l.startswith(brand_l + " "):
            core = model
        else:
            core = f"{brand} {model}"
    else:
        core = brand or model
    year_tokens = {t.lower() for t in core.split() if t}
    if year and year.lower() not in year_tokens and year != model:
        core = f"{core} {year}".strip() if core else year
    if not core and _filled(vehicle.get("text")):
        return str(vehicle["text"]).strip()
    return core or None
