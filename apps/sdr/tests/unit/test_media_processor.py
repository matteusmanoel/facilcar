"""Unit tests for media processor (mocked OpenAI)."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sdr.config import get_settings
from sdr.media.image_describer import contains_forbidden_claims, sanitize_description
from sdr.media.processor import MediaContentType, process_media
from sdr.domain.document_storage import build_document_storage_key, resolve_documents_bucket
from sdr.infrastructure.storage_client import (
    BotoObjectStore,
    DocumentsBucketNotConfigured,
    get_documents_bucket,
    is_storage_configured,
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
        '{"name":"Maria Silva","cpf":"12345678909","birth_date":"1990-01-15",'
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
    assert result.extracted.cpf == "12345678909"
    assert result.extracted.name == "Maria Silva"


@pytest.mark.asyncio
async def test_document_pdf_routes_to_extractor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sdr.media.document_extractor.rasterize_pdf_first_page",
        lambda data, **kwargs: b"\xff\xd8\xfffakejpeg",
    )
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


def test_storage_not_configured_without_private_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "STORAGE_ENDPOINT",
        "STORAGE_ACCESS_KEY",
        "STORAGE_SECRET_KEY",
        "SDR_DOCUMENTS_BUCKET",
    ):
        monkeypatch.delenv(key, raising=False)
    assert not is_storage_configured()
    with pytest.raises(DocumentsBucketNotConfigured):
        get_documents_bucket()
    assert resolve_documents_bucket("vehicle-images") is None
    assert resolve_documents_bucket("sdr-documents") == "sdr-documents"


def test_build_document_storage_key_shape() -> None:
    key = build_document_storage_key(
        conversation_id="syn-conv-doc-1",
        provider_message_id="syn-prov-doc-1",
        document_type="CNH",
        content_hash="abc123def456",
        extension="pdf",
    )
    assert key == "sdr-documents/syn-conv-doc-1/syn-prov-doc-1_cnh_abc123def456.pdf"
    assert "customer-documents" not in key
    assert "vehicle-images" not in key


def test_configured_upload_failure_does_not_fall_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STORAGE_ENDPOINT", "https://s3.example")
    monkeypatch.setenv("STORAGE_ACCESS_KEY", "ak")
    monkeypatch.setenv("STORAGE_SECRET_KEY", "sk")
    monkeypatch.setenv("STORAGE_BUCKET_NAME", "vehicle-images")
    monkeypatch.setenv("SDR_DOCUMENTS_BUCKET", "sdr-documents")

    class Boom:
        def put_object(self, **kwargs):
            raise RuntimeError("NoSuchBucket")

    monkeypatch.setattr(
        "sdr.infrastructure.storage_client._s3_client",
        lambda: Boom(),
    )
    store = BotoObjectStore()
    with pytest.raises(RuntimeError, match="NoSuchBucket"):
        store.put_object(
            bucket="sdr-documents",
            key="sdr-documents/syn/key.pdf",
            body=b"doc-bytes",
            content_type="application/pdf",
        )
    with pytest.raises(DocumentsBucketNotConfigured):
        store.put_object(
            bucket="vehicle-images",
            key="customer-documents/x.pdf",
            body=b"doc-bytes",
        )
