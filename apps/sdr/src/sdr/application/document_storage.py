"""Persist inbound documents to the private SDR bucket — never the catalog bucket."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from sdr.domain.document_storage import (
    STORAGE_PERMANENT_FAILURE,
    STORAGE_PROCESSING,
    STORAGE_RETRYABLE_FAILURE,
    STORAGE_STORED,
    build_document_storage_key,
    classify_empty_payload,
    classify_storage_error,
    content_hash_for,
    resolve_documents_bucket,
    sanitize_storage_error,
)
from sdr.infrastructure.storage_client import extension_for_mime

logger = logging.getLogger("sdr.document_storage")


class ObjectStore(Protocol):
    def put_object(
        self,
        *,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str | None = None,
    ) -> None: ...

    def head_object(self, *, bucket: str, key: str) -> dict | None: ...


class DocumentRecords(Protocol):
    async def upsert_inbound(self, **fields: Any) -> dict: ...


class MessageRecords(Protocol):
    async def set_media_storage_key(self, message_id: str, key: str | None) -> None: ...


@dataclass(slots=True)
class StoreDocumentRequest:
    data: bytes
    mime_type: str | None
    document_type: str
    conversation_id: str
    message_id: str
    provider_message_id: str
    lead_id: str | None = None
    extracted_json: dict[str, Any] | None = None
    extraction_ok: bool = False


@dataclass(slots=True)
class DocumentStorageOutcome:
    commercial_received: bool
    document_type: str
    storage_status: str
    storage_key: str | None
    storage_bucket: str | None
    media_storage_key: str | None
    document_id: str | None
    customer_error_exposed: bool = False
    attempts: int = 0
    sanitized_error: str | None = None
    buckets_attempted: list[str] = field(default_factory=list)


def _log(
    *,
    operation: str,
    bucket: str | None,
    key: str | None,
    status: str,
    attempt: int,
    error: BaseException | None = None,
) -> None:
    payload = {
        "operation": operation,
        "bucket": bucket,
        "key": (key or "")[:120],
        "status": status,
        "attempt": attempt,
    }
    if error is not None:
        payload["exception_type"] = type(error).__name__
        http = getattr(error, "response", None)
        if isinstance(http, dict):
            meta = http.get("ResponseMetadata") or {}
            payload["http_status"] = meta.get("HTTPStatusCode")
            payload["request_id"] = meta.get("RequestId")
            err = http.get("Error") or {}
            payload["provider_code"] = err.get("Code")
    logger.info("document_storage %s", payload)


class DocumentStorageService:
    def __init__(
        self,
        *,
        object_store: ObjectStore,
        documents: DocumentRecords,
        messages: MessageRecords,
        settings: Any,
    ) -> None:
        self._store = object_store
        self._documents = documents
        self._messages = messages
        self._settings = settings

    def _bucket(self) -> str | None:
        configured = getattr(self._settings, "sdr_documents_bucket", None) or ""
        return resolve_documents_bucket(configured)

    def _max_attempts(self) -> int:
        return max(1, int(getattr(self._settings, "sdr_document_storage_max_attempts", 3) or 3))

    async def store_inbound_document(
        self, req: StoreDocumentRequest
    ) -> DocumentStorageOutcome:
        doc_type = (req.document_type or "OTHER").upper()
        commercial = bool(req.data)
        if classify_empty_payload(req.data) == STORAGE_PERMANENT_FAILURE:
            outcome = DocumentStorageOutcome(
                commercial_received=False,
                document_type=doc_type,
                storage_status=STORAGE_PERMANENT_FAILURE,
                storage_key=None,
                storage_bucket=self._bucket(),
                media_storage_key=None,
                document_id=None,
                sanitized_error="empty_payload",
            )
            _log(
                operation="store",
                bucket=outcome.storage_bucket,
                key=None,
                status=outcome.storage_status,
                attempt=0,
            )
            return outcome

        bucket = self._bucket()
        digest = content_hash_for(req.data)
        ext = extension_for_mime(req.mime_type)
        key = build_document_storage_key(
            conversation_id=req.conversation_id,
            provider_message_id=req.provider_message_id,
            document_type=doc_type,
            content_hash=digest,
            extension=ext,
        )
        attempted: list[str] = []
        prev = await self._previous_row(req)
        prev_attempts = int(
            (prev or {}).get("storage_attempts")
            or (prev or {}).get("storageAttempts")
            or 0
        )
        attempts = prev_attempts + 1
        if not bucket:
            status = STORAGE_RETRYABLE_FAILURE
            err = "documents_bucket_not_configured"
            _log(
                operation="store",
                bucket=None,
                key=key,
                status=status,
                attempt=0,
            )
            row = await self._safe_upsert(
                req,
                doc_type=doc_type,
                bucket=None,
                key=None,
                status=status,
                attempts=attempts,
                error=err,
                digest=digest,
            )
            if attempts >= self._max_attempts():
                status = STORAGE_PERMANENT_FAILURE
            return DocumentStorageOutcome(
                commercial_received=commercial,
                document_type=doc_type,
                storage_status=status,
                storage_key=None,
                storage_bucket=None,
                media_storage_key=None,
                document_id=row.get("id") if row else None,
                attempts=attempts,
                sanitized_error=err,
                buckets_attempted=attempted,
            )

        existing = self._store.head_object(bucket=bucket, key=key)
        put_needed = existing is None
        status = STORAGE_PROCESSING
        error_text: str | None = None
        if put_needed:
            attempted.append(bucket)
            try:
                self._store.put_object(
                    bucket=bucket,
                    key=key,
                    body=req.data,
                    content_type=req.mime_type,
                )
                status = STORAGE_STORED
            except Exception as exc:
                status = classify_storage_error(exc)
                error_text = sanitize_storage_error(exc)
                _log(
                    operation="put_object",
                    bucket=bucket,
                    key=key,
                    status=status,
                    attempt=attempts,
                    error=exc,
                )
        else:
            status = STORAGE_STORED

        persist_key = key if status == STORAGE_STORED else None
        row = await self._safe_upsert(
            req,
            doc_type=doc_type,
            bucket=bucket,
            key=persist_key,
            status=status,
            attempts=attempts,
            error=error_text,
            digest=digest,
        )
        if status == STORAGE_STORED and not row:
            status = STORAGE_RETRYABLE_FAILURE
            error_text = error_text or "metadata_persist_failed"
            persist_key = None
            _log(
                operation="upsert_inbound",
                bucket=bucket,
                key=key,
                status=status,
                attempt=attempts,
            )

        media_key = None
        if status == STORAGE_STORED and persist_key:
            try:
                await self._messages.set_media_storage_key(req.message_id, persist_key)
                media_key = persist_key
            except Exception as exc:
                status = STORAGE_RETRYABLE_FAILURE
                error_text = sanitize_storage_error(exc)
                persist_key = None
                _log(
                    operation="set_media_storage_key",
                    bucket=bucket,
                    key=key,
                    status=status,
                    attempt=attempts,
                    error=exc,
                )

        if attempts >= self._max_attempts() and status == STORAGE_RETRYABLE_FAILURE:
            status = STORAGE_PERMANENT_FAILURE

        _log(
            operation="store",
            bucket=bucket,
            key=key,
            status=status,
            attempt=attempts,
        )
        return DocumentStorageOutcome(
            commercial_received=commercial,
            document_type=doc_type,
            storage_status=status,
            storage_key=persist_key if status == STORAGE_STORED else None,
            storage_bucket=bucket,
            media_storage_key=media_key,
            document_id=row.get("id") if row else None,
            attempts=attempts,
            sanitized_error=error_text,
            buckets_attempted=attempted,
        )

    async def _safe_upsert(
        self,
        req: StoreDocumentRequest,
        *,
        doc_type: str,
        bucket: str | None,
        key: str | None,
        status: str,
        attempts: int,
        error: str | None,
        digest: str,
    ) -> dict:
        try:
            return await self._documents.upsert_inbound(
                conversation_id=req.conversation_id,
                message_id=req.message_id,
                provider_message_id=req.provider_message_id,
                lead_id=req.lead_id,
                document_type=doc_type,
                storage_key=key,
                storage_bucket=bucket,
                storage_status=status,
                storage_attempts=attempts,
                storage_error=error,
                mime_type=req.mime_type,
                byte_size=len(req.data or b""),
                extracted_json=req.extracted_json,
                extraction_status="DONE" if req.extraction_ok else "FAILED",
                content_hash=digest,
            )
        except Exception as exc:
            _log(
                operation="upsert_inbound",
                bucket=bucket,
                key=key,
                status=STORAGE_RETRYABLE_FAILURE,
                attempt=attempts,
                error=exc,
            )
            return {}

    async def _previous_row(self, req: StoreDocumentRequest) -> dict:
        getter = getattr(self._documents, "get_by_provider", None)
        if getter is None:
            return {}
        try:
            row = await getter(req.conversation_id, req.provider_message_id)
        except Exception:
            return {}
        if row is None:
            return {}
        if isinstance(row, dict):
            return row
        try:
            return dict(row)
        except Exception:
            return {}
