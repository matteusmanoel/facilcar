"""Ranking: structured engine exact vs unknown vs incompatible vs title fallback."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sdr.domain.inventory_search import build_inventory_search_request
from sdr.tools.inventory import EngineMatch, InventoryVehicle, MatchTier, select_ranked_vehicles


def _v(**overrides: Any) -> InventoryVehicle:
    base = dict(
        id="v1",
        slug="x",
        title="TOYOTA COROLLA",
        brand_name="Toyota",
        model="Corolla",
        type="CAR",
        price_cash=Decimal("90000"),
        mileage=None,
        color=None,
        year_model=2016,
        year_manufacture=2015,
        version="GLI",
        engine_displacement_liters=None,
    )
    base.update(overrides)
    return InventoryVehicle(**base)


def _req(engine: float | None = 2.0):
    facts: dict[str, Any] = {"desired_model": "corolla"}
    if engine is not None:
        facts["desired_engine_displacement_liters"] = engine
    return build_inventory_search_request(facts)


def test_confirmed_2_0_ranks_above_1_8() -> None:
    v20 = _v(id="c20", engine_displacement_liters=Decimal("2.0"), title="COROLLA GLI 2.0")
    v18 = _v(id="c18", engine_displacement_liters=Decimal("1.8"), title="COROLLA GLI 1.8")
    ranked = select_ranked_vehicles([v18, v20], _req(2.0))
    assert ranked[0].id == "c20"
    assert ranked[0].engine_match == EngineMatch.EXACT
    assert ranked[0].match_tier == MatchTier.STRUCTURED_MODEL_ENGINE_EXACT


def test_unknown_engine_below_confirmed_2_0() -> None:
    confirmed = _v(id="c20", engine_displacement_liters=Decimal("2.0"))
    unknown = _v(id="unk", engine_displacement_liters=None, title="TOYOTA COROLLA GLI")
    ranked = select_ranked_vehicles([unknown, confirmed], _req(2.0))
    assert [v.id for v in ranked[:2]] == ["c20", "unk"]
    assert ranked[0].engine_match == EngineMatch.EXACT
    assert ranked[1].engine_match == EngineMatch.UNKNOWN
    assert ranked[1].match_tier == MatchTier.STRUCTURED_MODEL_ENGINE_UNKNOWN


def test_suspicious_model_title_corolla_2_0_is_fallback() -> None:
    dirty = _v(
        id="view",
        model="View",
        title="TOYOTA COROLLA GLI 2.0 AUTOMÁTICO • 2016",
        engine_displacement_liters=None,
    )
    ranked = select_ranked_vehicles([dirty], _req(2.0))
    assert ranked[0].id == "view"
    assert ranked[0].match_tier == MatchTier.TITLE_MODEL_ENGINE_EXACT
    assert ranked[0].engine_match == EngineMatch.UNKNOWN
    assert ranked[0].to_dict()["engineDisplacementLiters"] is None


def test_different_engine_only_as_alternative() -> None:
    confirmed = _v(id="c20", engine_displacement_liters=Decimal("2.0"))
    other = _v(id="c18", engine_displacement_liters=Decimal("1.8"))
    ranked = select_ranked_vehicles([other, confirmed], _req(2.0))
    assert ranked[0].id == "c20"
    alts = [v for v in ranked if v.engine_match == EngineMatch.INCOMPATIBLE]
    assert [v.id for v in alts] == ["c18"]
    assert alts[0].match_tier == MatchTier.ENGINE_INCOMPATIBLE_ALTERNATIVE


def test_title_2_0_does_not_confirm_persisted_engine() -> None:
    v = _v(
        id="x",
        title="TOYOTA COROLLA GLI 2.0",
        engine_displacement_liters=None,
    )
    ranked = select_ranked_vehicles([v], _req(2.0))
    assert ranked[0].to_dict()["engineDisplacementLiters"] is None
    assert ranked[0].engine_match == EngineMatch.UNKNOWN


def test_published_only_contract_still_in_sql() -> None:
    from sdr.tools import inventory as inv

    assert inv._CANDIDATE_SQL.count("'PUBLISHED'") == 1
    assert "engineDisplacementLiters" in inv._CANDIDATE_SQL
    assert "DRAFT" not in inv._CANDIDATE_SQL
