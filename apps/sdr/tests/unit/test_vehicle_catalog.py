"""Catalog enrichment — not for intent classification."""

from __future__ import annotations

from sdr.domain.vehicle_catalog import brands_compatible, enrich_vehicle, split_brand_model


def test_ka_enriches_ford() -> None:
    out = enrich_vehicle({"model": "Ka"})
    assert out["brand"] == "Ford"
    assert out["model"] == "Ka"


def test_ford_ka_splits() -> None:
    brand, model = split_brand_model("Ford Ka")
    assert brand == "Ford"
    assert model == "Ka"


def test_honda_corolla_incompatible() -> None:
    assert brands_compatible("Honda", "Corolla") is False
    assert brands_compatible("Toyota", "Corolla") is True


def test_incompatible_brand_replaced_from_catalog() -> None:
    out = enrich_vehicle({"model": "Corolla", "brand": "Honda"})
    assert out["brand"] == "Toyota"
