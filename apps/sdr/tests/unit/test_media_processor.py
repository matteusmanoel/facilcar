"""Unit tests for media processor (mocked OpenAI)."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sdr.config import get_settings
from sdr.media.image_describer import contains_forbidden_claims, sanitize_description
from sdr.media.processor import MediaContentType, process_media
from sdr.infrastructure.storage_client import (
    build_storage_key,
    is_storage_configured,
    upload_document,
)


@pytest.fixture(autouse=True)
def _clear_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["OPENAI_API_KEY"] = ""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _mock_transcription_client(text: str) -> MagicMock:
    client = MagicMock()
    client.audio.transcriptions.create = MagicMock(
        return_value=SimpleNamespace(text=text)
    )
    return client


def _mock_vision_client(content: str) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = MagicMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
    )
    return client


@pytest.mark.asyncio
async def test_audio_transcription() -> None:
    client = _mock_transcription_client("Quero financiar um Onix 2022")
    result = await process_media(
        b"fake-audio-bytes",
        content_type=MediaContentType.AUDIO,
        mime_type="audio/ogg",
        client=client,
    )
    assert result.text == "Quero financiar um Onix 2022"
    assert result.routed_as == "audio_transcriber"
    client.audio.transcriptions.create.assert_called_once()


@pytest.mark.asyncio
async def test_image_no_mechanical_claims() -> None:
    # Model might overreach; sanitize + assert no forbidden fabrication keywords.
    client = _mock_vision_client(
        "Carro prata visto de frente. Preço de mercado R$ 50.000 e sinistro leve."
    )
    result = await process_media(
        b"fake-image-bytes",
        content_type="IMAGE",
        mime_type="image/jpeg",
        client=client,
    )
    assert result.description
    assert result.routed_as == "image_describer"
    assert not contains_forbidden_claims(result.description)
    lower = result.description.lower()
    assert "preço" not in lower
    assert "sinistro" not in lower
    assert "garantia" not in lower
    assert "km" not in lower


def test_sanitize_strips_forbidden_sentences() -> None:
    raw = "Veículo branco na foto. Valor de mercado alto. Ângulo frontal."
    cleaned = sanitize_description(raw)
    assert "valor de mercado" not in cleaned.lower()
    assert "branco" in cleaned.lower() or "frontal" in cleaned.lower()


@pytest.mark.asyncio
async def test_image_as_document_routes_to_extractor() -> None:
    payload = (
        '{"name":"Maria Silva","cpf":"12345678901","birth_date":"1990-01-15",'
        '"plate":null,"document_type":"CNH"}'
    )
    client = _mock_vision_client(payload)
    result = await process_media(
        b"fake-cnh",
        content_type=MediaContentType.IMAGE,
        mime_type="image/jpeg",
        as_document=True,
        client=client,
    )
    assert result.routed_as == "document_extractor"
    assert result.extracted is not None
    assert result.extracted.document_type == "CNH"
    assert result.extracted.cpf == "12345678901"
    assert result.extracted.name == "Maria Silva"


@pytest.mark.asyncio
async def test_document_pdf_routes_to_extractor() -> None:
    payload = (
        '{"name":null,"cpf":null,"birth_date":null,"plate":"ABC1D23",'
        '"document_type":"CRLV"}'
    )
    client = _mock_vision_client(payload)
    result = await process_media(
        b"%PDF-fake",
        content_type=MediaContentType.DOCUMENT,
        mime_type="application/pdf",
        client=client,
    )
    assert result.routed_as == "document_extractor"
    assert result.extracted is not None
    assert result.extracted.plate == "ABC1D23"
    assert result.extracted.document_type == "CRLV"


def test_storage_stub_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "STORAGE_ENDPOINT",
        "STORAGE_ACCESS_KEY",
        "STORAGE_SECRET_KEY",
        "SDR_DOCUMENTS_BUCKET",
    ):
        monkeypatch.delenv(key, raising=False)
    assert not is_storage_configured()
    uploaded = upload_document(
        b"doc-bytes",
        lead_id="lead_abc",
        document_type="CNH",
        mime_type="image/jpeg",
    )
    assert uploaded.stub is True
    assert uploaded.storage_key.startswith("stub/lead_abc/cnh_")
    assert uploaded.storage_key.endswith(".jpg")
    assert uploaded.bucket == "sdr-documents"


def test_build_storage_key_shape() -> None:
    key = build_storage_key(
        "lead1",
        "INCOME_PROOF",
        extension="pdf",
        timestamp=1724628000,
        rand="a3b2c1",
    )
    assert key == "lead1/income_proof_1724628000_a3b2c1.pdf"
