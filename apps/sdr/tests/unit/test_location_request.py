"""Protocol-deterministic store location request."""

from __future__ import annotations

from sdr.domain.location_request import has_store_location_request_evidence


def test_location_request_is_protocol_not_product_list() -> None:
    assert has_store_location_request_evidence("Qual a localização da loja?")
    assert has_store_location_request_evidence("Onde vocês ficam?")
    assert has_store_location_request_evidence("Me manda o endereço")
    assert has_store_location_request_evidence("como chego aí?")
    assert not has_store_location_request_evidence("Fiquei interessado no Corolla")
    assert not has_store_location_request_evidence("Olá, tudo bem?")


def test_location_text_omits_maps_link_when_pin_exists() -> None:
    from sdr.tools.location import format_location_text, get_location_pin

    settings = {
        "siteName": "FácilCar Multimarcas",
        "addressLine": "R. Ipanema, 1206 - Periolo",
        "city": "Cascavel",
        "state": "PR",
        "zipCode": "85817-020",
        "latitude": -24.9378419,
        "longitude": -53.420055,
    }
    pin = get_location_pin(settings)
    assert pin is not None
    text = format_location_text(settings, include_maps_link=False)
    assert "maps.google.com" not in text
    assert "Ipanema" in text
    assert "85817-020" in text
