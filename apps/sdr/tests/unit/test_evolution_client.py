"""Unit tests for EvolutionClient (httpx + respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from sdr.config import Settings
from sdr.infrastructure.evolution_client import (
    EvolutionClient,
    EvolutionError,
    EvolutionUnauthorizedError,
)


def _settings(**overrides: str) -> Settings:
    data = {
        "evolution_api_url": "http://evolution.test",
        "evolution_api_key": "test-api-key",
        "evolution_sdr_instance": "facilcar-sdr",
        "database_url": "postgresql://unused:unused@localhost:5432/unused",
        "redis_url": "redis://localhost:6379/15",
        "sdr_webhook_secret": "test-secret",
    }
    data.update(overrides)
    return Settings(**data)


@pytest.mark.asyncio
@respx.mock
async def test_send_text_sends_apikey_header_and_returns_message_id() -> None:
    route = respx.post("http://evolution.test/message/sendText/facilcar-sdr").mock(
        return_value=httpx.Response(
            200,
            json={"key": {"id": "MSG-ABC-123", "fromMe": True}},
        )
    )
    async with EvolutionClient(settings=_settings()) as client:
        mid = await client.send_text("5545988432998", "Olá!", delay_ms=800)

    assert mid == "MSG-ABC-123"
    assert route.called
    request = route.calls.last.request
    assert request.headers.get("apikey") == "test-api-key"
    body = request.read()
    assert b'"delay": 800' in body or b'"delay":800' in body
    assert b"5545988432998" in body


@pytest.mark.asyncio
@respx.mock
async def test_send_text_401_raises_unauthorized() -> None:
    respx.post("http://evolution.test/message/sendText/facilcar-sdr").mock(
        return_value=httpx.Response(401, json={"statusCode": 401, "error": "Unauthorized"})
    )
    async with EvolutionClient(settings=_settings()) as client:
        with pytest.raises(EvolutionUnauthorizedError) as exc:
            await client.send_text("5545988432998", "oi")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_send_media_success() -> None:
    respx.post("http://evolution.test/message/sendMedia/facilcar-sdr").mock(
        return_value=httpx.Response(200, json={"key": {"id": "MEDIA-1"}})
    )
    async with EvolutionClient(settings=_settings()) as client:
        mid = await client.send_media(
            "5545988432998",
            "image",
            "https://cdn.example/car.jpg",
            "image/jpeg",
            "Foto do veículo",
        )
    assert mid == "MEDIA-1"


@pytest.mark.asyncio
@respx.mock
async def test_download_media_base64_post() -> None:
    route = respx.post(
        "http://evolution.test/chat/getBase64FromMediaMessage/facilcar-sdr"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"base64": "aGVsbG8=", "mimetype": "image/jpeg"},
        )
    )
    async with EvolutionClient(settings=_settings()) as client:
        result = await client.download_media_base64(
            {
                "key": {"id": "IN-1"},
                "message": {"imageMessage": {"mimetype": "image/jpeg"}},
            }
        )
    assert result["base64"] == "aGVsbG8="
    assert result["mimetype"] == "image/jpeg"
    assert route.called
    assert route.calls.last.request.headers.get("apikey") == "test-api-key"


@pytest.mark.asyncio
@respx.mock
async def test_check_instance() -> None:
    respx.get("http://evolution.test/instance/connectionState/facilcar-sdr").mock(
        return_value=httpx.Response(200, json={"instance": {"state": "open"}})
    )
    async with EvolutionClient(settings=_settings()) as client:
        state = await client.check_instance()
    assert state["instance"]["state"] == "open"


@pytest.mark.asyncio
@respx.mock
async def test_other_4xx_raises_evolution_error() -> None:
    respx.post("http://evolution.test/message/sendText/facilcar-sdr").mock(
        return_value=httpx.Response(500, text="boom")
    )
    async with EvolutionClient(settings=_settings()) as client:
        with pytest.raises(EvolutionError) as exc:
            await client.send_text("5545988432998", "oi")
    assert exc.value.status_code == 500
