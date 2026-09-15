"""Phase 13A — document bucket fail-closed before any object-store call."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sdr.application.document_storage import DocumentStorageService, StoreDocumentRequest
from sdr.config import Settings
from sdr.domain.document_storage import STORAGE_RETRYABLE_FAILURE, resolve_documents_bucket
from sdr.domain.runtime_settings import RuntimeConfigError, validate_runtime_settings
from sdr.infrastructure.storage_client import DocumentsBucketNotConfigured, get_documents_bucket


class RecordingStore:
    def __init__(self) -> None:
        self.put_calls: list[tuple[str, str]] = []
        self.head_calls: list[tuple[str, str]] = []

    def put_object(self, *, bucket: str, key: str, body: bytes, content_type: str | None = None) -> None:
        _ = (body, content_type)
        self.put_calls.append((bucket, key))

    def head_object(self, *, bucket: str, key: str) -> dict | None:
        self.head_calls.append((bucket, key))
        return None


class MemoryDocs:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def upsert_inbound(self, **fields):
        self.rows.append(fields)
        return {"id": "doc-1", **fields}


class MemoryMessages:
    def __init__(self) -> None:
        self.keys: dict[str, str] = {}

    async def set_media_storage_key(self, message_id: str, key: str | None) -> None:
        if key:
            self.keys[message_id] = key


def _settings(**overrides: object) -> Settings:
    data: dict[str, object] = {
        "database_url": "postgresql://unused:unused@localhost:5432/unused",
        "redis_url": "redis://localhost:6379/15",
        "sdr_webhook_secret": "not-a-placeholder",
        "sdr_environment": "sandbox",
        "sdr_outbound_policy": "deny_all",
        "sdr_documents_bucket": "",
        "storage_endpoint": "",
        "storage_access_key": "",
        "storage_secret_key": "",
    }
    data.update(overrides)
    return Settings(**data)


def test_staging_without_bucket_fails_closed() -> None:
    with pytest.raises(RuntimeConfigError):
        validate_runtime_settings(
            _settings(
                sdr_environment="staging",
                sdr_outbound_policy="allowlist",
                sdr_outbound_allowlist="5511999000101",
            )
        )


def test_production_without_bucket_fails_closed() -> None:
    with pytest.raises(RuntimeConfigError):
        validate_runtime_settings(
            _settings(
                sdr_environment="production",
                sdr_outbound_policy="unrestricted",
            )
        )


def test_vehicle_images_is_refused_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDR_DOCUMENTS_BUCKET", "vehicle-images")
    assert resolve_documents_bucket("vehicle-images") is None
    with pytest.raises(DocumentsBucketNotConfigured) as exc:
        get_documents_bucket()
    assert "vehicle-images" in str(exc.value)
    assert "secret" not in str(exc.value).lower() or "must be set" in str(exc.value)


@pytest.mark.asyncio
async def test_invalid_bucket_does_not_call_store_or_mark_media_success() -> None:
    store = RecordingStore()
    docs = MemoryDocs()
    messages = MemoryMessages()
    service = DocumentStorageService(
        object_store=store,
        documents=docs,
        messages=messages,
        settings=SimpleNamespace(sdr_documents_bucket="vehicle-images", sdr_document_storage_max_attempts=1),
    )
    outcome = await service.store_inbound_document(
        StoreDocumentRequest(
            data=b"%PDF-1.4 test",
            mime_type="application/pdf",
            document_type="CNH",
            conversation_id="c1",
            message_id="m1",
            provider_message_id="p1",
        )
    )
    assert store.put_calls == []
    assert store.head_calls == []
    assert outcome.storage_status == STORAGE_RETRYABLE_FAILURE
    assert outcome.media_storage_key is None
    assert outcome.commercial_received is True
    assert outcome.customer_error_exposed is False
    assert "m1" not in messages.keys


def test_explicit_test_bucket_does_not_open_network() -> None:
    assert resolve_documents_bucket("sdr-documents-test") == "sdr-documents-test"
