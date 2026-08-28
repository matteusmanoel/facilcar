"""Vehicle presentation contract — photos + caption, never a text listing."""

from __future__ import annotations

from sdr.domain.photo_request import has_photo_request_evidence
from sdr.domain.vehicle_presentation import (
    format_price_brl,
    format_vehicle_caption,
    media_items_from_images,
    media_items_from_vehicles,
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
    assert "TOYOTA COROLLA GLI 2.0 AUTOMÁTICO • 2016" in caption
    assert "R$ 84.900" in caption
    assert "160.000" in caption
    assert "Motor" in caption
    assert "não consta" not in caption.lower()
    assert "Cor:" not in caption
    assert "84900.0" not in caption
    assert "Conforto e estilo sem igual." in caption


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
