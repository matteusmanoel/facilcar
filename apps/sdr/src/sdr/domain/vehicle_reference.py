"""Resolve an inbound reference to a presented vehicle — never by list position."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from sdr.domain.inbound import QuotedContext

RESOLUTION_EXPLICIT_REPLY = "explicit_reply"
RESOLUTION_LISTING = "listing_reference"
RESOLUTION_UNIQUE_CONTEXT = "unique_recent"
RESOLUTION_AMBIGUOUS = "ambiguous"
RESOLUTION_NONE = "none"

_DEMONSTRATIVE = re.compile(
    r"\b(ess[ea]|est[ea]|isso|aquele|aquela|dessa opção|dessa|desse|"
    r"this one|that one)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PresentedVehicleBinding:
    conversation_id: str
    provider_message_id: str
    vehicle_id: str
    presentation_type: str
    position: int = 0
    offer_set_id: str | None = None
    media_url: str | None = None
    created_at: float | None = None
    content_sha256: str | None = None
    dhash: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "provider_message_id": self.provider_message_id,
            "vehicle_id": self.vehicle_id,
            "presentation_type": self.presentation_type,
            "position": self.position,
            "offer_set_id": self.offer_set_id,
            "media_url": self.media_url,
            "created_at": self.created_at,
            "content_sha256": self.content_sha256,
            "dhash": self.dhash,
        }

    @classmethod
    def from_mapping(cls, raw: Any) -> PresentedVehicleBinding | None:
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, dict):
            return None
        conv = str(raw.get("conversation_id") or "").strip()
        provider = str(raw.get("provider_message_id") or "").strip()
        vehicle = str(raw.get("vehicle_id") or "").strip()
        if not conv or not provider or not vehicle:
            return None
        try:
            position = int(raw.get("position") or 0)
        except (TypeError, ValueError):
            position = 0
        created = raw.get("created_at")
        try:
            created_at = float(created) if created is not None else None
        except (TypeError, ValueError):
            created_at = None
        sha = str(raw.get("content_sha256") or "").strip() or None
        dhash = str(raw.get("dhash") or raw.get("perceptual_hash") or "").strip() or None
        return cls(
            conversation_id=conv,
            provider_message_id=provider,
            vehicle_id=vehicle,
            presentation_type=str(raw.get("presentation_type") or "IMAGE"),
            position=position,
            offer_set_id=(str(raw["offer_set_id"]) if raw.get("offer_set_id") else None),
            media_url=(str(raw["media_url"]).strip() if raw.get("media_url") else None),
            created_at=created_at,
            content_sha256=sha,
            dhash=dhash,
        )


@dataclass(frozen=True, slots=True)
class VehicleReferenceResolution:
    vehicle_id: str | None
    reason: str
    binding: PresentedVehicleBinding | None = None
    occurred_at: float | None = None


def upsert_presented_binding(state: Any, binding: PresentedVehicleBinding) -> None:
    """Append a presented-vehicle binding; same conversation+provider id is a no-op."""
    existing = bindings_from_state(getattr(state, "presented_vehicle_bindings", None))
    key = (binding.conversation_id, binding.provider_message_id)
    if any((b.conversation_id, b.provider_message_id) == key for b in existing):
        return
    existing.append(binding)
    state.presented_vehicle_bindings = [item.as_dict() for item in existing]


def bindings_from_state(raw: Iterable[Any] | None) -> list[PresentedVehicleBinding]:
    out: list[PresentedVehicleBinding] = []
    for item in raw or []:
        parsed = PresentedVehicleBinding.from_mapping(item)
        if parsed:
            out.append(parsed)
    return out


def bindings_for_offer_set(
    bindings: Sequence[PresentedVehicleBinding],
    offer_set_id: str,
) -> list[PresentedVehicleBinding]:
    return [b for b in bindings if b.offer_set_id == offer_set_id]


def _scope(
    bindings: Sequence[PresentedVehicleBinding], conversation_id: str
) -> list[PresentedVehicleBinding]:
    return [b for b in bindings if b.conversation_id == conversation_id]


def _unique_vehicle_ids(bindings: Sequence[PresentedVehicleBinding]) -> list[str]:
    seen: list[str] = []
    for binding in bindings:
        if binding.vehicle_id not in seen:
            seen.append(binding.vehicle_id)
    return seen


def _has_demonstrative(text: str | None) -> bool:
    return bool(_DEMONSTRATIVE.search(text or ""))


def resolve_vehicle_reference(
    *,
    conversation_id: str,
    quoted: Sequence[QuotedContext] | None,
    bindings: Sequence[PresentedVehicleBinding],
    last_shown_vehicle_ids: Sequence[str] | None = None,
    inbound_text: str = "",
    listing_id: str | None = None,
    inbound_media_url: str | None = None,
    inbound_timestamp: float | None = None,
) -> VehicleReferenceResolution:
    """Priority: explicit reply → listing/url → unique recent context → ambiguous."""
    scoped = _scope(bindings, conversation_id)
    shown = [str(v) for v in (last_shown_vehicle_ids or []) if str(v).strip()]

    def _result(
        vehicle_id: str | None,
        reason: str,
        binding: PresentedVehicleBinding | None = None,
    ) -> VehicleReferenceResolution:
        return VehicleReferenceResolution(
            vehicle_id=vehicle_id,
            reason=reason,
            binding=binding,
            occurred_at=inbound_timestamp,
        )

    for quote in quoted or []:
        stanza = (quote.stanza_id or "").strip()
        if not stanza:
            continue
        matches = [b for b in scoped if b.provider_message_id == stanza]
        if len(matches) == 1:
            return _result(matches[0].vehicle_id, RESOLUTION_EXPLICIT_REPLY, matches[0])
        if len(matches) > 1:
            ids = _unique_vehicle_ids(matches)
            if len(ids) == 1:
                return _result(ids[0], RESOLUTION_EXPLICIT_REPLY, matches[0])

    listing = (listing_id or "").strip()
    if listing:
        listed = [b for b in scoped if b.vehicle_id == listing]
        if listed:
            return _result(listing, RESOLUTION_LISTING, listed[0])
        if listing in shown:
            return _result(listing, RESOLUTION_LISTING)

    media_url = (inbound_media_url or "").strip()
    if media_url:
        url_matches = [
            b for b in scoped if (b.media_url or "").strip() == media_url
        ]
        ids = _unique_vehicle_ids(url_matches)
        if len(ids) == 1:
            return _result(ids[0], RESOLUTION_LISTING, url_matches[0])

    unique_ids = _unique_vehicle_ids(scoped) or list(shown)
    if len(unique_ids) == 1 and _has_demonstrative(inbound_text):
        only = unique_ids[0]
        binding = next((b for b in scoped if b.vehicle_id == only), None)
        return _result(only, RESOLUTION_UNIQUE_CONTEXT, binding)

    if len(unique_ids) > 1 and _has_demonstrative(inbound_text):
        return _result(None, RESOLUTION_AMBIGUOUS)

    if quoted:
        return _result(None, RESOLUTION_NONE)
    if media_url or (inbound_text and len(unique_ids) > 1):
        return _result(None, RESOLUTION_AMBIGUOUS)
    return _result(None, RESOLUTION_NONE)


def apply_primary_vehicle_choice(state: Any, resolved: VehicleReferenceResolution) -> None:
    """Set explicit primary. Older timestamps cannot overwrite a newer choice."""
    vehicle_id = resolved.vehicle_id
    if not vehicle_id:
        return
    ts = resolved.occurred_at
    chosen_at = getattr(state, "primary_vehicle_chosen_at", None)
    if ts is None:
        ts = (chosen_at + 1) if isinstance(chosen_at, (int, float)) else 0.0
    if (
        getattr(state, "primary_vehicle_id", None)
        and isinstance(chosen_at, (int, float))
        and isinstance(ts, (int, float))
        and ts < chosen_at
    ):
        return
    if getattr(state, "primary_vehicle_id", None) == vehicle_id:
        if getattr(state, "primary_vehicle_chosen_at", None) is None:
            state.primary_vehicle_chosen_at = ts
        return
    state.primary_vehicle_id = vehicle_id
    state.primary_vehicle_chosen_at = ts
    shown = list(getattr(state, "last_shown_vehicle_ids", None) or [])
    if vehicle_id not in shown:
        shown.append(vehicle_id)
        state.last_shown_vehicle_ids = shown


def apply_primary_from_inbound(
    state: Any,
    *,
    conversation_id: str,
    quoted: Sequence[QuotedContext] | None,
    inbound_text: str = "",
    listing_id: str | None = None,
    inbound_media_url: str | None = None,
    inbound_timestamp: float | None = None,
) -> VehicleReferenceResolution:
    bindings = bindings_from_state(getattr(state, "presented_vehicle_bindings", None))
    resolved = resolve_vehicle_reference(
        conversation_id=conversation_id,
        quoted=quoted,
        bindings=bindings,
        last_shown_vehicle_ids=getattr(state, "last_shown_vehicle_ids", None),
        inbound_text=inbound_text,
        listing_id=listing_id,
        inbound_media_url=inbound_media_url,
        inbound_timestamp=inbound_timestamp,
    )
    apply_primary_vehicle_choice(state, resolved)
    return resolved


def select_explicit_primary_id(rows: Sequence[dict[str, Any]]) -> str | None:
    """CRM/API: only an explicit isPrimary flag. Never the first row."""
    for row in rows:
        if not row.get("isPrimary"):
            continue
        vid = str(row.get("vehicleId") or row.get("vehicle_id") or "").strip()
        if vid:
            return vid
    return None


def next_primary_vehicle_id(
    *,
    selected_ids: Sequence[str],
    current_primary_id: str | None,
) -> str | None:
    """Keep the current primary if still selected; never default to index 0."""
    ids = [str(v).strip() for v in selected_ids if str(v).strip()]
    current = (current_primary_id or "").strip()
    if current and current in ids:
        return current
    return None
