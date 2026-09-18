"""Phase 13A — Evolution HTTP is not attempted when the phone is denied."""

from __future__ import annotations

import httpx
import pytest
import respx

from sdr.config import Settings
from sdr.domain.phone_access import OutboundDeniedError
from sdr.infrastructure.evolution_client import EvolutionClient

ALLOWED = "5511999000101"
DENIED = "5511999000199"


def _settings(**overrides: object) -> Settings:
    data: dict[str, object] = {
        "evolution_api_url": "http://evolution.test",
        "evolution_api_key": "test-api-key",
        "evolution_sdr_instance": "facilcar-sdr",
        "database_url": "postgresql://unused:unused@localhost:5432/unused",
        "redis_url": "redis://localhost:6379/15",
        "sdr_webhook_secret": "test-secret",
        "sdr_environment": "staging",
        "sdr_outbound_policy": "allowlist",
        "sdr_outbound_allowlist": ALLOWED,
        "sdr_documents_bucket": "sdr-documents-test",
    }
    data.update(overrides)
    return Settings(**data)


@pytest.mark.asyncio
@respx.mock
async def test_denied_phone_does_not_call_evolution_for_text() -> None:
    route = respx.post("http://evolution.test/message/sendText/facilcar-sdr").mock(
        return_value=httpx.Response(200, json={"key": {"id": "SHOULD-NOT-SEND"}})
    )
    async with EvolutionClient(settings=_settings()) as client:
        with pytest.raises(OutboundDeniedError) as exc:
            await client.send_text(DENIED, "oi")
    assert route.called is False
    assert DENIED not in str(exc.value)


@pytest.mark.asyncio
@respx.mock
async def test_denied_phone_blocks_image_document_and_location() -> None:
    media = respx.post("http://evolution.test/message/sendMedia/facilcar-sdr").mock(
        return_value=httpx.Response(200, json={"key": {"id": "MEDIA"}})
    )
    loc = respx.post("http://evolution.test/message/sendLocation/facilcar-sdr").mock(
        return_value=httpx.Response(200, json={"key": {"id": "LOC"}})
    )
    async with EvolutionClient(settings=_settings()) as client:
        with pytest.raises(OutboundDeniedError):
            await client.send_media(DENIED, "image", "https://cdn.example/a.jpg", "image/jpeg")
        with pytest.raises(OutboundDeniedError):
            await client.send_media(DENIED, "document", "https://cdn.example/a.pdf", "application/pdf")
        with pytest.raises(OutboundDeniedError):
            await client.send_location(DENIED, latitude=-25.5, longitude=-54.5)
    assert media.called is False
    assert loc.called is False


@pytest.mark.asyncio
@respx.mock
async def test_allowed_phone_still_sends_when_explicitly_listed() -> None:
    route = respx.post("http://evolution.test/message/sendText/facilcar-sdr").mock(
        return_value=httpx.Response(200, json={"key": {"id": "MSG-OK"}})
    )
    async with EvolutionClient(settings=_settings()) as client:
        mid = await client.send_text(ALLOWED, "oi")
    assert mid == "MSG-OK"
    assert route.called is True
