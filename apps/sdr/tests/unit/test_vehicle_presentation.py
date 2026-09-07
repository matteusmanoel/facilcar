"""Vehicle presentation contract — photos + caption, never a text listing."""

from __future__ import annotations

from sdr.domain.photo_request import has_photo_request_evidence
from sdr.domain.vehicle_presentation import (
    format_price_brl,
    format_vehicle_caption,
    media_items_from_images,
    media_items_from_vehicles,
    order_images_cover_last,
)


def test_price_formats_brazilian_reais() -> None:
    assert format_price_brl(84900.0) == "R$ 84.900"
    assert format_price_brl(None) is None


def test_caption_uses_published_fields_and_omits_missing() -> None:
    caption = format_vehicle_caption(
        {
            "title": "TOYOTA COROLLA GLI 2.0 AUTOMÁTICO",
            "yearModel": 2016,
            "priceCash": 84900,
            "mileage": 160000,
            "color": None,
            "engineDisplacementLiters": 2.0,
        }
    )
    assert "🚗" in caption
    assert "*TOYOTA COROLLA GLI 2.0 AUTOMÁTICO • 2016*" in caption
    assert "R$ 84.900" in caption
    assert "160.000" in caption
    assert "Motor" in caption
    assert "não consta" not in caption.lower()
    assert "Cor:" not in caption
    assert "84900.0" not in caption
    assert "conforto e estilo sem igual" not in caption.lower()


def test_caption_on_last_photo_only() -> None:
    images = [
        {"url": "https://cdn.example/a.jpg", "sortOrder": 0},
        {"url": "https://cdn.example/b.jpg", "sortOrder": 1},
        {"url": "https://cdn.example/c.jpg", "sortOrder": 2},
    ]
    items = media_items_from_images(images, caption="Corolla completo", vehicle_id="v1")
    assert len(items) == 3
    assert items[0].caption == ""
    assert items[1].caption == ""
    assert items[2].caption == "Corolla completo"


def test_cover_survives_cap_and_is_last() -> None:
    images = [
        {"url": "https://cdn.example/cover.jpg", "sortOrder": 0, "isCover": True},
        {"url": "https://cdn.example/1.jpg", "sortOrder": 1, "isCover": False},
        {"url": "https://cdn.example/2.jpg", "sortOrder": 2, "isCover": False},
        {"url": "https://cdn.example/3.jpg", "sortOrder": 3, "isCover": False},
        {"url": "https://cdn.example/4.jpg", "sortOrder": 4, "isCover": False},
        {"url": "https://cdn.example/5.jpg", "sortOrder": 5, "isCover": False},
    ]
    from sdr.domain.vehicle_presentation import select_images_for_send

    capped = select_images_for_send(images, limit=5)
    assert len(capped) == 5
    assert capped[-1]["url"].endswith("cover.jpg")
    items = media_items_from_images(images, caption="caption", vehicle_id="v1", limit=5)
    assert len(items) == 5
    assert items[-1].url.endswith("cover.jpg")
    all_six = media_items_from_images(images, caption="caption", vehicle_id="v1")
    assert len(all_six) == 6
    assert all_six[-1].url.endswith("cover.jpg")
    assert all_six[-1].caption == "caption"


def test_cover_image_is_sent_last() -> None:
    images = [
        {"url": "https://cdn.example/cover.jpg", "sortOrder": 0, "isCover": True},
        {"url": "https://cdn.example/a.jpg", "sortOrder": 1, "isCover": False},
        {"url": "https://cdn.example/b.jpg", "sortOrder": 2, "isCover": False},
    ]
    ordered = order_images_cover_last(images)
    assert ordered[-1]["url"].endswith("cover.jpg")
    items = media_items_from_images(images, caption="caption", vehicle_id="v1")
    assert items[-1].url.endswith("cover.jpg")
    assert items[-1].caption == "caption"
    assert items[0].caption == ""


def test_single_vehicle_uses_all_photos() -> None:
    vehicle = {
        "id": "v1",
        "title": "Honda Civic EXL",
        "yearModel": 2019,
        "priceCash": 79900,
        "images": [
            {"url": "https://cdn.example/1.jpg", "sortOrder": 0},
            {"url": "https://cdn.example/2.jpg", "sortOrder": 1},
        ],
    }
    items = media_items_from_vehicles([vehicle])
    assert len(items) == 2
    assert items[0].caption == ""
    assert "Honda Civic" in items[1].caption
    assert "R$ 79.900" in items[1].caption


def test_photo_request_is_protocol_not_product_list() -> None:
    assert has_photo_request_evidence("TOP! Esse mesmo, tem fotos?")
    assert has_photo_request_evidence("Pode mandar as imagens desse carro")
    assert has_photo_request_evidence("manda as fotos por aqui")
    assert not has_photo_request_evidence("Gostaria de ver um corolla que vi no estoque")
    assert not has_photo_request_evidence("Olá, tudo bem?")


def test_seed_cards_identify_vehicle_and_translate_transmission() -> None:
    from tests.golden.fixtures.seed_inventory_adapter import load_seed

    seed = {row["id"]: row for row in load_seed()}
    onix = format_vehicle_caption(seed["VH-PUBLISHED-005"])
    hb20 = format_vehicle_caption(seed["VH-PUBLISHED-004"])
    cronos = format_vehicle_caption(seed["VH-PUBLISHED-001"])
    sold = format_vehicle_caption(seed["VH-SOLD-CIVIC-001"])
    for caption in (onix, hb20, cronos, sold):
        assert "veículo publicado" not in caption.lower()
        assert "automatic" not in caption.lower()
    assert "Onix" in onix
    assert "automático" in onix
    assert "HB20" in hb20
    assert "Cronos" in cronos
    assert "Civic" in sold
    models = {row["model"].lower() for row in load_seed()}
    assert "gol" not in models
    assert "fox" not in models

