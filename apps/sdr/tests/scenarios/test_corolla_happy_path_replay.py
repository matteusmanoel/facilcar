"""Replay: Corolla happy path + Civic installment tightness (mocked inventory)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from sdr.application.process_turn import process_turn
from sdr.domain.types import ConversationCanonicalState, CustomerState
from sdr.replay import (
    _check_turn_assertions,
    _make_deterministic_understand,
    inbound_from_fixture_turn,
)
from sdr.tools.inventory import InventoryVehicle, select_ranked_vehicles


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _corolla() -> InventoryVehicle:
    return InventoryVehicle(
        id="cmsuev4980026vm24shr68ui1",
        slug="corolla-gli",
        title="TOYOTA COROLLA GLI 2.0 AUTOMÁTICO",
        brand_name="Toyota",
        model="Corolla",
        type="CAR",
        price_cash=Decimal("84900"),
        mileage=160000,
        color=None,
        year_model=2016,
        year_manufacture=2015,
        version="GLI",
        images=(
            {"id": "img1", "url": "https://cdn.example/corolla-1.jpg", "sortOrder": 0, "isCover": True},
            {"id": "img2", "url": "https://cdn.example/corolla-2.jpg", "sortOrder": 1, "isCover": False},
            {"id": "img3", "url": "https://cdn.example/corolla-3.jpg", "sortOrder": 2, "isCover": False},
            {"id": "img4", "url": "https://cdn.example/corolla-4.jpg", "sortOrder": 3, "isCover": False},
            {"id": "img5", "url": "https://cdn.example/corolla-5.jpg", "sortOrder": 4, "isCover": False},
            {"id": "img6", "url": "https://cdn.example/corolla-6.jpg", "sortOrder": 5, "isCover": False},
        ),
    )


def _civic() -> InventoryVehicle:
    return InventoryVehicle(
        id="civic-1",
        slug="civic",
        title="HONDA CIVIC EXL",
        brand_name="Honda",
        model="Civic",
        type="CAR",
        price_cash=Decimal("84900"),
        mileage=42000,
        color="Prata",
        year_model=2019,
        year_manufacture=2018,
        version="EXL",
        images=(
            {"id": "c1", "url": "https://cdn.example/civic-cover.jpg", "sortOrder": 0, "isCover": True},
            {"id": "c2", "url": "https://cdn.example/civic-2.jpg", "sortOrder": 1, "isCover": False},
        ),
    )


def _onix() -> InventoryVehicle:
    return InventoryVehicle(
        id="onix-1",
        slug="onix",
        title="CHEVROLET ONIX LT",
        brand_name="Chevrolet",
        model="Onix",
        type="CAR",
        price_cash=Decimal("55900"),
        mileage=30000,
        color=None,
        year_model=2020,
        year_manufacture=2019,
        version="LT",
        images=(),
    )


async def _run_fixture(monkeypatch, fixture_name: str, stock: list[InventoryVehicle], thread_id: str) -> None:
    async def fake_search(pool, req):
        return select_ranked_vehicles(stock, req)

    async def fake_get(pool, vehicle_id):
        for car in stock:
            if car.id == vehicle_id:
                return car
        return None

    async def fake_images(pool, vehicle_id, *, limit=12):
        for car in stock:
            if car.id == vehicle_id:
                return list(car.images)[:limit]
        return []

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)
    monkeypatch.setattr("sdr.tools.inventory.get_vehicle_by_id", fake_get)
    monkeypatch.setattr("sdr.tools.send_photos.fetch_vehicle_image_urls", fake_images)

    data = yaml.safe_load((FIXTURES / fixture_name).read_text())
    turns = data["turns"]
    understand, _ = _make_deterministic_understand(turns)
    state = ConversationCanonicalState(
        thread_id=thread_id,
        customer=CustomerState(phone="554588230845"),
    )
    turn_assertions = {int(ta["turn"]): ta for ta in data.get("turn_assertions") or []}
    customer_turn = 0

    for turn in turns:
        if turn.get("role") != "customer":
            continue
        if turn.get("command") == "reset_memory":
            state = ConversationCanonicalState(
                thread_id=state.thread_id,
                customer=state.customer,
            )
            continue

        customer_turn += 1
        coalesce = turn.get("coalesce")
        if isinstance(coalesce, list) and coalesce:
            text = "\n".join(str(p.get("text") or "") for p in coalesce)
        else:
            text = str(turn.get("text") or "")

        before = state
        inbound = inbound_from_fixture_turn(turn, text, state.thread_id)
        if inbound is not None:
            result = await process_turn(
                state=state,
                inbound=inbound,
                understand=understand,
                pool=object(),
            )
        else:
            result = await process_turn(
                state=state,
                inbound_text=text,
                understand=understand,
                pool=object(),
            )
        if result.outbound_texts or result.outbound_media:
            result.state.assistant_turn_count = state.assistant_turn_count + 1
        state = result.state

        ta = turn_assertions.get(customer_turn)
        if ta:
            failures = _check_turn_assertions(customer_turn, ta, result, before)
            assert not failures, failures


@pytest.mark.asyncio
async def test_corolla_happy_path_replay(monkeypatch) -> None:
    await _run_fixture(monkeypatch, "corolla_happy_path.yaml", [_corolla()], "corolla-happy")


@pytest.mark.asyncio
async def test_civic_installment_tight_semantic_equivalent(monkeypatch) -> None:
    await _run_fixture(
        monkeypatch,
        "civic_installment_tight.yaml",
        [_civic(), _onix()],
        "civic-tight",
    )
