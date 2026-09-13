"""SDR document upload via S3-compatible API — private documents bucket only."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sdr.domain.document_storage import FORBIDDEN_DOCUMENT_BUCKETS, resolve_documents_bucket

logger = logging.getLogger(__name__)


class DocumentsBucketNotConfigured(RuntimeError):
    """SDR_DOCUMENTS_BUCKET missing or points at the public catalog bucket."""


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
    """Private documents bucket. Never falls back to ``vehicle-images``."""
    bucket = resolve_documents_bucket(_env("SDR_DOCUMENTS_BUCKET"))
    if not bucket:
        raise DocumentsBucketNotConfigured(
            "SDR_DOCUMENTS_BUCKET must be set to a private documents bucket"
        )
    return bucket


def is_storage_configured() -> bool:
    return bool(
        _env("STORAGE_ENDPOINT")
        and _env("STORAGE_ACCESS_KEY")
        and _env("STORAGE_SECRET_KEY")
        and resolve_documents_bucket(_env("SDR_DOCUMENTS_BUCKET"))
    )


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


class BotoObjectStore:
    """S3-compatible adapter used by DocumentStorageService."""

    def put_object(
        self,
        *,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str | None = None,
    ) -> None:
        if bucket in FORBIDDEN_DOCUMENT_BUCKETS:
            raise DocumentsBucketNotConfigured(
                "refusing to upload customer documents to the catalog bucket"
            )
        extra: dict[str, Any] = {}
        if content_type:
            extra["ContentType"] = content_type
        _s3_client().put_object(Bucket=bucket, Key=key, Body=body or b"", **extra)

    def head_object(self, *, bucket: str, key: str) -> dict | None:
        try:
            resp = _s3_client().head_object(Bucket=bucket, Key=key)
        except Exception as exc:
            code = ""
            response = getattr(exc, "response", None)
            if isinstance(response, dict):
                code = str((response.get("Error") or {}).get("Code") or "")
            if code in {"404", "NoSuchKey", "NotFound"} or "404" in str(exc):
                return None
            raise
        return {"content_length": resp.get("ContentLength")}
