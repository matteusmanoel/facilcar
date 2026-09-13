"""Async Evolution API v2.3.7 client (httpx).

Auth: header ``apikey`` (not Bearer). Instance: ``EVOLUTION_SDR_INSTANCE``.
"""

from __future__ import annotations

from typing import Any

import httpx

from sdr.config import Settings, get_settings


class EvolutionError(Exception):
    """Base Evolution client error."""

    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class EvolutionUnauthorizedError(EvolutionError):
    """Raised when Evolution returns HTTP 401."""


def _extract_message_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    key = payload.get("key")
    if isinstance(key, dict):
        mid = key.get("id")
        if isinstance(mid, str) and mid.strip():
            return mid.strip()
    for field in ("messageId", "id", "providerMessageId"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _guess_filename(mediatype: str, mimetype: str, media: str) -> str:
    if media.startswith("http://") or media.startswith("https://"):
        path = media.split("?", 1)[0].rstrip("/")
        name = path.rsplit("/", 1)[-1]
        if "." in name:
            return name
    subtype = mimetype.split("/", 1)[-1] if "/" in mimetype else "bin"
    subtype = subtype.split("+", 1)[0] or "bin"
    return f"{mediatype or 'file'}.{subtype}"


class EvolutionClient:
    """Thin async wrapper around Evolution message/chat/instance endpoints."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._settings = settings or get_settings()
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    @property
    def base_url(self) -> str:
        return (self._settings.evolution_api_url or "").rstrip("/")

    @property
    def instance(self) -> str:
        return self._settings.evolution_sdr_instance

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "apikey": self._settings.evolution_api_key or "",
        }

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> EvolutionClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        response = await self._client.request(
            method,
            url,
            headers=self._headers(),
            json=json,
        )
        body_text = response.text
        if response.status_code == 401:
            raise EvolutionUnauthorizedError(
                "Evolution API unauthorized",
                status_code=401,
                body=body_text[:500],
            )
        if response.status_code >= 400:
            raise EvolutionError(
                f"Evolution API error {response.status_code}",
                status_code=response.status_code,
                body=body_text[:500],
            )
        if not body_text.strip():
            return None
        try:
            return response.json()
        except ValueError:
            return body_text

    async def send_text(
        self,
        number: str,
        text: str,
        delay_ms: int = 800,
    ) -> str | None:
        """Send a plain-text WhatsApp message via Evolution.

        Returns the provider message id when present in the Evolution response.

        Persistence contract: the caller must persist a reserved ``isBotSent``
        row **before** this call, then update ``providerMessageId`` to the
        returned id when present. That marker lets inbound ``fromMe`` webhooks
        distinguish bot-sent traffic from human seller replies.
        """
        payload = await self._request(
            "POST",
            f"/message/sendText/{self.instance}",
            json={
                "number": number,
                "text": text,
                "delay": delay_ms,
            },
        )
        return _extract_message_id(payload)

    async def send_location(
        self,
        number: str,
        *,
        latitude: float,
        longitude: float,
        name: str = "",
        address: str = "",
        delay_ms: int = 800,
    ) -> str | None:
        """Send a WhatsApp location pin via Evolution ``/message/sendLocation``."""
        payload = await self._request(
            "POST",
            f"/message/sendLocation/{self.instance}",
            json={
                "number": number,
                "name": name or "FacilCar",
                "address": address or "",
                "latitude": float(latitude),
                "longitude": float(longitude),
                "delay": delay_ms,
            },
        )
        return _extract_message_id(payload)

    async def send_media(
        self,
        number: str,
        mediatype: str,
        media_url_or_base64: str,
        mimetype: str,
        caption: str = "",
        *,
        file_name: str | None = None,
        delay_ms: int | None = None,
    ) -> str | None:
        """Send media (image/video/document/audio). ``media`` may be URL or base64."""
        body: dict[str, Any] = {
            "number": number,
            "mediatype": mediatype,
            "mimetype": mimetype,
            "media": media_url_or_base64,
            "caption": caption or "",
            "fileName": file_name
            or _guess_filename(mediatype, mimetype, media_url_or_base64),
        }
        if delay_ms is not None:
            body["delay"] = delay_ms
        payload = await self._request(
            "POST",
            f"/message/sendMedia/{self.instance}",
            json=body,
        )
        return _extract_message_id(payload)

    async def download_media_base64(self, raw_message_ref: dict[str, Any]) -> dict[str, Any]:
        """Download inbound media as base64 (Evolution v2.3.7 chat controller).

        Uses ``POST /chat/getBase64FromMediaMessage/{instance}`` — the path
        documented for GET/POST in Evolution v2; this stack uses POST (same as
        the catalog-import TypeScript client).

        ``raw_message_ref`` may be:
        - a full webhook message object with ``key`` / ``message``
        - a catalog-style ``{type, message}`` mediaRef
        - an already-wrapped ``{message: {...}}`` body
        """
        body = _build_base64_request_body(raw_message_ref)
        payload = await self._request(
            "POST",
            f"/chat/getBase64FromMediaMessage/{self.instance}",
            json=body,
        )
        if not isinstance(payload, dict) or not payload.get("base64"):
            raise EvolutionError("Evolution media response missing base64")
        return {
            "base64": payload["base64"],
            "mimetype": payload.get("mimetype") or payload.get("mimeType") or "application/octet-stream",
        }

    async def check_instance(self) -> dict[str, Any]:
        """Return instance connection state (``GET /instance/connectionState/{instance}``)."""
        payload = await self._request(
            "GET",
            f"/instance/connectionState/{self.instance}",
        )
        if isinstance(payload, dict):
            return payload
        return {"raw": payload}


def _build_base64_request_body(raw_message_ref: dict[str, Any]) -> dict[str, Any]:
    """Normalize various media-ref shapes into Evolution's expected body."""
    if "convertToMp4" in raw_message_ref and "message" in raw_message_ref:
        return dict(raw_message_ref)

    # Full webhook / Baileys message: { key, message }
    if "key" in raw_message_ref and "message" in raw_message_ref:
        return {
            "message": {
                "key": raw_message_ref.get("key") or {},
                "message": raw_message_ref.get("message") or {},
            },
            "convertToMp4": False,
        }

    # Catalog mediaRef: { type: "imageMessage", message: { ... } }
    msg_type = raw_message_ref.get("type")
    nested = raw_message_ref.get("message")
    if isinstance(msg_type, str) and isinstance(nested, dict):
        return {
            "message": {
                "key": raw_message_ref.get("key") or {},
                "message": {msg_type: nested},
            },
            "convertToMp4": False,
        }

    # Already wrapped: { message: { key?, message? } }
    inner = raw_message_ref.get("message")
    if isinstance(inner, dict) and ("key" in inner or "message" in inner):
        return {"message": inner, "convertToMp4": False}

    return {
        "message": {
            "key": raw_message_ref.get("key") or {},
            "message": nested if isinstance(nested, dict) else raw_message_ref,
        },
        "convertToMp4": False,
    }
