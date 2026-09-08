"""Apply visual vehicle resolution onto canonical state during a turn."""

from __future__ import annotations

from typing import Any, Mapping

from sdr.config import get_settings
from sdr.domain.image_fingerprint import parse_dhash, sha256_hex
from sdr.domain.inbound import ContentType, InboundTurn
from sdr.domain.types import ConversationCanonicalState
from sdr.domain.vehicle_reference import (
    RESOLUTION_EXPLICIT_REPLY,
    RESOLUTION_LISTING,
    VehicleReferenceResolution,
    bindings_from_state,
    resolve_vehicle_reference,
)
from sdr.domain.visual_resolution import (
    FingerprintRecord,
    InventoryCandidate,
    ObservedAttributes,
    VisualVehicleResolution,
    apply_visual_resolution,
    fingerprints_from_bindings,
    resolve_visual_vehicle,
)


def _records_from_ref(raw: Mapping[str, Any] | None) -> list[FingerprintRecord]:
    payload = (raw or {}).get("image_index") or (raw or {}).get("fingerprints") or []
    out: list[FingerprintRecord] = []
    if not isinstance(payload, list):
        return out
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        vid = str(item.get("vehicle_id") or "").strip()
        if not vid:
            continue
        out.append(
            FingerprintRecord(
                vehicle_id=vid,
                conversation_id=str(item.get("conversation_id") or "catalog"),
                sha256=(str(item.get("sha256") or item.get("content_sha256") or "").strip() or None),
                dhash=parse_dhash(item.get("dhash")),
                model=(str(item["model"]) if item.get("model") else None),
                brand=(str(item["brand"]) if item.get("brand") else None),
                status=(str(item["status"]) if item.get("status") else None),
            )
        )
    return out


async def _candidate_lookup(attrs: ObservedAttributes, pool: Any) -> list[InventoryCandidate]:
    if pool is None:
        return []
    from sdr.domain.inventory_search import InventorySearchRequest
    from sdr.tools.inventory import search_with_request

    text = " ".join(p for p in (attrs.brand, attrs.model) if p)
    req = InventorySearchRequest(
        original_model=attrs.model,
        original_brand=attrs.brand,
        original_vehicle_text=text or None,
        limit=5,
    )
    vehicles = await search_with_request(pool, req)
    out: list[InventoryCandidate] = []
    for v in vehicles or []:
        out.append(
            InventoryCandidate(
                vehicle_id=v.id,
                status=getattr(v, "status", None) or "PUBLISHED",
                model=v.model,
                brand=v.brand_name,
                title=v.title,
            )
        )
    return out


async def enrich_state_with_visual(
    state: ConversationCanonicalState,
    inbound: InboundTurn,
    *,
    image_bytes: bytes | None = None,
    pool: Any = None,
    quoted_resolution: VehicleReferenceResolution | None = None,
) -> VisualVehicleResolution:
    ref = inbound.raw_message_ref if isinstance(inbound.raw_message_ref, dict) else {}
    pre = ref.get("visual_resolution")
    if isinstance(pre, dict) and pre.get("resolution_source"):
        vis = VisualVehicleResolution.from_mapping(pre)
        apply_visual_resolution(
            state,
            vis,
            inbound_text=inbound.effective_text,
            inbound_timestamp=inbound.timestamp,
        )
        ref["visual_resolution"] = vis.to_dict()
        inbound.raw_message_ref = ref
        return vis

    is_image = bool(image_bytes) or inbound.content_type == ContentType.IMAGE
    explicit = bool(
        quoted_resolution
        and quoted_resolution.vehicle_id
        and quoted_resolution.reason in (RESOLUTION_EXPLICIT_REPLY, RESOLUTION_LISTING)
    )
    if not is_image and not explicit:
        return VisualVehicleResolution.from_mapping(state.last_visual_resolution)

    if image_bytes:
        digest = sha256_hex(image_bytes)
        prev = VisualVehicleResolution.from_mapping(state.last_visual_resolution)
        if prev.content_sha256 == digest and prev.resolver_version:
            prev.vision_calls = 0
            apply_visual_resolution(
                state,
                prev,
                inbound_text=inbound.effective_text,
                inbound_timestamp=inbound.timestamp,
            )
            ref["visual_resolution"] = prev.to_dict()
            inbound.raw_message_ref = ref
            return prev

    fingerprints = fingerprints_from_bindings(bindings_from_state(state.presented_vehicle_bindings))
    fingerprints.extend(_records_from_ref(ref))

    vision_fn = None
    lookup = None
    settings = get_settings()
    allow_vision = bool((settings.openai_api_key or "").strip()) and image_bytes
    if allow_vision:
        from sdr.media.image_describer import extract_visual_observation

        async def vision_fn(data: bytes, mime: str | None):
            return await extract_visual_observation(data, mime_type=mime)

        if pool is not None:
            async def lookup(attrs: ObservedAttributes):
                return await _candidate_lookup(attrs, pool)

    vis = await resolve_visual_vehicle(
        conversation_id=state.thread_id,
        quoted=quoted_resolution,
        inbound_text=inbound.effective_text,
        fingerprints=fingerprints,
        image_bytes=image_bytes,
        declared_mime=inbound.mime_type,
        vision=vision_fn,
        candidate_lookup=lookup,
        vision_model=settings.sdr_vision_model,
        allow_vision=bool(allow_vision),
    )
    apply_visual_resolution(
        state,
        vis,
        inbound_text=inbound.effective_text,
        inbound_timestamp=inbound.timestamp,
    )
    ref["visual_resolution"] = vis.to_dict()
    fp = ref.get("media_fingerprint") if isinstance(ref.get("media_fingerprint"), dict) else {}
    if image_bytes and not fp:
        ref["media_fingerprint"] = {
            "sha256": sha256_hex(image_bytes),
            "byte_size": len(image_bytes),
        }
    inbound.raw_message_ref = ref
    return vis


def quoted_resolution_from_inbound(
    state: ConversationCanonicalState,
    inbound: InboundTurn,
) -> VehicleReferenceResolution:
    listing_id = None
    media_url = None
    ref = inbound.raw_message_ref or {}
    if ref:
        listing_id = ref.get("listing_id") or ref.get("listing_url")
        media_url = ref.get("media_url") or ref.get("url")
    return resolve_vehicle_reference(
        conversation_id=state.thread_id,
        quoted=inbound.quoted,
        bindings=bindings_from_state(state.presented_vehicle_bindings),
        last_shown_vehicle_ids=state.last_shown_vehicle_ids,
        inbound_text=inbound.effective_text,
        listing_id=str(listing_id) if listing_id else state.listing_reference,
        inbound_media_url=str(media_url) if media_url else None,
        inbound_timestamp=inbound.timestamp,
    )
