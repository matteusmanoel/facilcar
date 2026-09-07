"""Replay: Corolla photos + deal_type follow-up (mocked inventory with images)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from sdr.application.process_turn import process_turn
from sdr.domain.types import Action, ConversationCanonicalState, CustomerState
from sdr.replay import _check_turn_assertions, _make_deterministic_understand
from sdr.tools.inventory import InventoryVehicle, select_ranked_vehicles


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

_COROLLA_IMAGES = (
    {"id": "img1", "url": "https://cdn.example/corolla-1.jpg", "sortOrder": 0, "isCover": True},
    {"id": "img2", "url": "https://cdn.example/corolla-2.jpg", "sortOrder": 1, "isCover": False},
    {"id": "img3", "url": "https://cdn.example/corolla-3.jpg", "sortOrder": 2, "isCover": False},
)


def _corolla() -> InventoryVehicle:
    return InventoryVehicle(
        id="cmsuev4980026vm24shr68ui1",
        slug="corolla-gli",
        title="TOYOTA COROLLA GLI 2.0 AUTOMÁTICO",
        brand_name="Toyota",
        model="Corolla",
        type="CAR",
        price_cash=Decimal("84900"),
        mileage=None,
        color=None,
        year_model=2016,
        year_manufacture=2015,
        version="GLI",
        images=_COROLLA_IMAGES,
    )


@pytest.mark.asyncio
async def test_corolla_photos_deal_type_replay(monkeypatch) -> None:
    stock = [_corolla()]

    async def fake_search(pool, req):
        return select_ranked_vehicles(stock, req)

    async def fake_get(pool, vehicle_id):
        car = _corolla()
        return car if car.id == vehicle_id else None

    async def fake_images(pool, vehicle_id, *, limit=12):
        car = _corolla()
        return list(car.images)[:limit] if car.id == vehicle_id else []

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)
    monkeypatch.setattr("sdr.tools.inventory.get_vehicle_by_id", fake_get)
    monkeypatch.setattr("sdr.tools.send_photos.fetch_vehicle_image_urls", fake_images)

    data = yaml.safe_load((FIXTURES / "corolla_photos_deal_type.yaml").read_text())
    turns = data["turns"]
    understand, _ = _make_deterministic_understand(turns)
    state = ConversationCanonicalState(
        thread_id="corolla-photos",
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

        if customer_turn == 2:
            assert result.action_plan.action == Action.SHOW_OFFERS
            assert len(result.outbound_media) == 3
            assert result.outbound_media[0].caption == ""
            assert "R$ 84.900" in result.outbound_media[-1].caption
            assert "*" in result.outbound_media[-1].caption
            assert result.outbound_media[-1].url.endswith("corolla-1.jpg")
            joined = " ".join(result.outbound_texts).lower()
            # "compra ou troca" must NOT be asked — intent is already PURCHASE
            assert "compra ou troca" not in joined
            assert "orçamento" not in joined
            assert "olha o que encontrei" not in joined
            assert state.last_shown_vehicle_ids == ["cmsuev4980026vm24shr68ui1"]

        if customer_turn == 3:
            assert result.action_plan.action == Action.SEND_PHOTOS
            assert result.outbound_media
            assert "whatsapp" not in " ".join(result.outbound_texts).lower()


@pytest.mark.asyncio
async def test_civic_images_semantic_variant(monkeypatch) -> None:
    """Same class of request with different vehicle and phrasing."""
    civic = InventoryVehicle(
        id="civic-1",
        slug="civic",
        title="HONDA CIVIC EXL",
        brand_name="Honda",
        model="Civic",
        type="CAR",
        price_cash=Decimal("79900"),
        mileage=42000,
        color="Prata",
        year_model=2019,
        year_manufacture=2018,
        version="EXL",
        images=(
            {"id": "c1", "url": "https://cdn.example/civic-1.jpg", "sortOrder": 0, "isCover": True},
            {"id": "c2", "url": "https://cdn.example/civic-2.jpg", "sortOrder": 1, "isCover": False},
        ),
    )

    async def fake_search(pool, req):
        return [civic]

    monkeypatch.setattr("sdr.tools.inventory.search_with_request", fake_search)

    from sdr.domain.types import BusinessIntent, TurnFacts

    state = ConversationCanonicalState(
        thread_id="civic-photos",
        customer=CustomerState(phone="5545999999999"),
        assistant_turn_count=1,
    )

    async def understand_interest(text, st):
        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            language="pt-BR",
            facts={"desired_model": "civic"},
        )

    r1 = await process_turn(
        state=state,
        inbound_text="Quero ver um civic que vi no site de vocês",
        understand=understand_interest,
        pool=object(),
    )
    assert r1.action_plan.action == Action.SHOW_OFFERS
    assert len(r1.outbound_media) == 2
    assert r1.outbound_media[0].caption == ""
    assert "HONDA CIVIC" in r1.outbound_media[-1].caption
    assert "*" in r1.outbound_media[-1].caption
    assert "R$ 79.900" in r1.outbound_media[-1].caption
    assert r1.outbound_media[-1].url.endswith("civic-1.jpg")
    joined = " ".join(r1.outbound_texts).lower()
    # "compra ou troca" must NOT be asked — intent is already PURCHASE
    assert "compra ou troca" not in joined
    assert "orçamento" not in joined
    assert "olha o que encontrei" not in joined

    async def understand_photos(text, st):
        from sdr.domain.photo_request import has_photo_request_evidence

        return TurnFacts(
            intent=BusinessIntent.PURCHASE,
            language="pt-BR",
            photo_request=has_photo_request_evidence(text) or None,
        )

    async def fake_get(pool, vehicle_id):
        return civic if vehicle_id == civic.id else None

    async def fake_images(pool, vehicle_id, *, limit=12):
        return list(civic.images)[:limit] if vehicle_id == civic.id else []

    monkeypatch.setattr("sdr.tools.inventory.get_vehicle_by_id", fake_get)
    monkeypatch.setattr("sdr.tools.send_photos.fetch_vehicle_image_urls", fake_images)

    r2 = await process_turn(
        state=r1.state,
        inbound_text="Pode mandar as imagens desse carro",
        understand=understand_photos,
        pool=object(),
    )
    assert r2.action_plan.action == Action.SEND_PHOTOS
    assert len(r2.outbound_media) == 2
    assert r2.outbound_media[-1].caption
    assert "orçamento" not in " ".join(r2.outbound_texts).lower()
