"""SDR document upload via S3-compatible API (same bucket as the web admin)."""

from __future__ import annotations

import logging
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "vehicle-images"
CUSTOMER_PREFIX = "customer-documents"


@dataclass(slots=True)
class UploadResult:
    storage_key: str
    bucket: str
    stub: bool
    byte_size: int
    uploaded: bool = True


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def get_documents_bucket() -> str:
    return (
        _env("STORAGE_BUCKET_NAME")
        or _env("SDR_DOCUMENTS_BUCKET")
        or DEFAULT_BUCKET
    )


def is_storage_configured() -> bool:
    return bool(
        _env("STORAGE_ENDPOINT")
        and _env("STORAGE_ACCESS_KEY")
        and _env("STORAGE_SECRET_KEY")
    )


def build_storage_key(
    customer_id: str,
    document_type: str,
    *,
    extension: str = "bin",
    timestamp: int | None = None,
    rand: str | None = None,
) -> str:
    """Path: customer-documents/{customerId}/{type}_{ts}_{rand}.ext"""
    ts = timestamp if timestamp is not None else int(time.time())
    suffix = rand if rand is not None else secrets.token_hex(3)
    doc = (document_type or "OTHER").strip().lower().replace(" ", "_")
    ext = extension.lstrip(".") or "bin"
    safe_owner = (customer_id or "unknown").strip() or "unknown"
    return f"{CUSTOMER_PREFIX}/{safe_owner}/{doc}_{ts}_{suffix}.{ext}"


def extension_for_mime(mime_type: str | None, filename: str | None = None) -> str:
    if filename:
        suffix = Path(filename).suffix.lstrip(".").lower()
        if suffix:
            return suffix
    if not mime_type:
        return "bin"
    mapping = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/pdf": "pdf",
        "application/pdf": "pdf",
        "audio/ogg": "ogg",
        "audio/mpeg": "mp3",
        "audio/mp4": "m4a",
    }
    return mapping.get(mime_type.lower(), "bin")


def _s3_client() -> Any:
    """Build boto3 S3 client matching web ``s3-client.ts`` env pattern."""
    import boto3
    from botocore.client import Config

    endpoint = _env("STORAGE_ENDPOINT")
    region = _env("STORAGE_S3_REGION", "auto") or "auto"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=_env("STORAGE_ACCESS_KEY"),
        aws_secret_access_key=_env("STORAGE_SECRET_KEY"),
        region_name=region,
        config=Config(s3={"addressing_style": "path"}),
    )


def upload_document(
    data: bytes,
    *,
    customer_id: str | None = None,
    document_type: str = "OTHER",
    mime_type: str | None = None,
    filename: str | None = None,
    force_stub: bool | None = None,
    lead_id: str | None = None,
) -> UploadResult:
    """Upload to the catalog bucket under ``customer-documents/{customerId}/``.

    ``lead_id`` is accepted as a legacy alias for ``customer_id``.
    If STORAGE_* is missing (or ``force_stub``), returns a stub key for tests.
    If storage is configured but upload fails, ``uploaded=False`` and empty key.
    """
    owner = (customer_id or lead_id or "unknown").strip() or "unknown"
    ext = extension_for_mime(mime_type, filename)
    key = build_storage_key(owner, document_type, extension=ext)
    bucket = get_documents_bucket()
    size = len(data or b"")

    use_stub = force_stub if force_stub is not None else not is_storage_configured()
    if use_stub:
        stub_key = f"stub/{key}"
        logger.debug("storage_client: stub upload key=%s size=%s", stub_key, size)
        return UploadResult(
            storage_key=stub_key,
            bucket=bucket,
            stub=True,
            byte_size=size,
            uploaded=False,
        )

    try:
        client = _s3_client()
        extra: dict[str, Any] = {}
        if mime_type:
            extra["ContentType"] = mime_type
        client.put_object(Bucket=bucket, Key=key, Body=data or b"", **extra)
    except Exception:
        logger.exception("storage_client: upload failed key=%s", key)
        return UploadResult(
            storage_key="",
            bucket=bucket,
            stub=False,
            byte_size=size,
            uploaded=False,
        )
    return UploadResult(
        storage_key=key,
        bucket=bucket,
        stub=False,
        byte_size=size,
        uploaded=True,
    )
