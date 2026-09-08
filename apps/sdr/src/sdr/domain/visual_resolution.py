"""Secure visual vehicle resolution — hierarchy before Vision.

The LLM never assigns vehicle_id. Code owns match / ambiguity / primary.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Mapping, Protocol, Sequence

from sdr.domain.image_fingerprint import (
    DHASH_MAX_DISTANCE,
    DHASH_MIN_MARGIN,
    RESOLVER_VERSION,
    hamming_distance,
    parse_dhash,
    sha256_hex,
)
from sdr.domain.media_safety import MediaSafetyResult, validate_image_bytes
from sdr.domain.types import ConversationCanonicalState
from sdr.domain.vehicle_reference import (
    RESOLUTION_EXPLICIT_REPLY,
    RESOLUTION_LISTING,
    RESOLUTION_NONE,
    RESOLUTION_UNIQUE_CONTEXT,
    PresentedVehicleBinding,
    VehicleReferenceResolution,
    apply_primary_vehicle_choice,
    bindings_from_state,
)

logger = logging.getLogger(__name__)

_DEMONSTRATIVE = re.compile(
    r"\b(ess[ea]|est[ea]|isso|aquele|aquela|dessa opção|dessa|desse|"
    r"this one|that one)\b",
    re.IGNORECASE,
)
_WEAK_VEHICLE_TEXT = re.compile(
    r"^(?:o\s+)?(?:ess[ea]|est[ea]|isso|aquele|aquela)\s+"
    r"(?:ve[ií]culo|carro|moto|op[cç][aã]o)?\s*$",
    re.IGNORECASE,
)
_INJECTION = re.compile(
    r"ignore(?:\s+all)?(?:\s+previous)?(?:\s+instructions)?|"
    r"you\s+are\s+now|system\s+prompt|handoff|decision\s+engine|"
    r"ignore\s+o\s+sistema|desconsidere\s+as\s+instru",
    re.I,
)


class VisualResolutionSource(str, Enum):
    QUOTED_MESSAGE = "quoted_message"
    LISTING_REFERENCE = "listing_reference"
    EXACT_MEDIA = "exact_media"
    PERCEPTUAL_MEDIA = "perceptual_media"
    VISION_INVENTORY_MATCH = "vision_inventory_match"
    ATTRIBUTES_ONLY = "attributes_only"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


SECURE_SOURCES = frozenset(
    {
        VisualResolutionSource.QUOTED_MESSAGE,
        VisualResolutionSource.LISTING_REFERENCE,
        VisualResolutionSource.EXACT_MEDIA,
        VisualResolutionSource.PERCEPTUAL_MEDIA,
        VisualResolutionSource.VISION_INVENTORY_MATCH,
    }
)


@dataclass(frozen=True, slots=True)
class FingerprintRecord:
    vehicle_id: str
    conversation_id: str = ""
    sha256: str | None = None
    dhash: int | None = None
    image_id: str | None = None
    url: str | None = None
    model: str | None = None
    brand: str | None = None
    status: str | None = None

    def in_scope(self, conversation_id: str) -> bool:
        if not self.conversation_id or self.conversation_id in {"*", "catalog"}:
            return True
        return self.conversation_id == conversation_id


@dataclass(frozen=True, slots=True)
class ObservedAttributes:
    is_vehicle: bool | None = None
    brand: str | None = None
    model: str | None = None
    color: str | None = None
    vehicle_type: str | None = None
    year: int | None = None
    overlay_text: str | None = None
    listing_screenshot: bool = False
    confidence: float = 0.0
    adversarial: bool = False

    def searchable(self) -> bool:
        if self.is_vehicle is False:
            return False
        if self.confidence < 0.5:
            return False
        return bool((self.model or "").strip() or (self.brand or "").strip())

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_vehicle": self.is_vehicle,
            "brand": self.brand,
            "model": self.model,
            "color": self.color,
            "vehicle_type": self.vehicle_type,
            "year": self.year,
            "listing_screenshot": self.listing_screenshot,
            "confidence": self.confidence,
            "adversarial": self.adversarial,
            "overlay_text_len": len(self.overlay_text or ""),
        }


@dataclass(frozen=True, slots=True)
class InventoryCandidate:
    vehicle_id: str
    status: str = "PUBLISHED"
    model: str | None = None
    brand: str | None = None
    title: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedMedia:
    sha256: str
    dhash: int | None
    mime_type: str | None
    byte_size: int
    safety: MediaSafetyResult


@dataclass(slots=True)
class VisualVehicleResolution:
    resolution_source: VisualResolutionSource
    confidence: float = 0.0
    candidate_vehicle_ids: tuple[str, ...] = ()
    matched_vehicle_id: str | None = None
    observed_attributes: dict[str, Any] = field(default_factory=dict)
    ambiguity_reason: str | None = None
    vision_attempted: bool = False
    vision_model: str | None = None
    fallback_reason: str | None = None
    match_margin: float | None = None
    vision_calls: int = 0
    latency_ms: float | None = None
    resolver_version: str = RESOLVER_VERSION
    catalog_status: str | None = None
    confirmed_label: str | None = None
    content_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution_source": self.resolution_source.value,
            "confidence": self.confidence,
            "candidate_vehicle_ids": list(self.candidate_vehicle_ids),
            "matched_vehicle_id": self.matched_vehicle_id,
            "observed_attributes": dict(self.observed_attributes),
            "ambiguity_reason": self.ambiguity_reason,
            "vision_attempted": self.vision_attempted,
            "vision_model": self.vision_model,
            "fallback_reason": self.fallback_reason,
            "match_margin": self.match_margin,
            "vision_calls": self.vision_calls,
            "latency_ms": self.latency_ms,
            "resolver_version": self.resolver_version,
            "catalog_status": self.catalog_status,
            "confirmed_label": self.confirmed_label,
            "content_sha256": self.content_sha256,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "VisualVehicleResolution":
        if not isinstance(raw, Mapping):
            return cls(resolution_source=VisualResolutionSource.UNRESOLVED)
        source_raw = str(raw.get("resolution_source") or VisualResolutionSource.UNRESOLVED.value)
        try:
            source = VisualResolutionSource(source_raw)
        except ValueError:
            source = VisualResolutionSource.UNRESOLVED
        ids = tuple(
            str(v) for v in (raw.get("candidate_vehicle_ids") or []) if str(v).strip()
        )
        return cls(
            resolution_source=source,
            confidence=float(raw.get("confidence") or 0),
            candidate_vehicle_ids=ids,
            matched_vehicle_id=(
                str(raw["matched_vehicle_id"]) if raw.get("matched_vehicle_id") else None
            ),
            observed_attributes=dict(raw.get("observed_attributes") or {}),
            ambiguity_reason=(str(raw["ambiguity_reason"]) if raw.get("ambiguity_reason") else None),
            vision_attempted=bool(raw.get("vision_attempted")),
            vision_model=(str(raw["vision_model"]) if raw.get("vision_model") else None),
            fallback_reason=(str(raw["fallback_reason"]) if raw.get("fallback_reason") else None),
            match_margin=(
                float(raw["match_margin"]) if raw.get("match_margin") is not None else None
            ),
            vision_calls=int(raw.get("vision_calls") or 0),
            latency_ms=(
                float(raw["latency_ms"]) if raw.get("latency_ms") is not None else None
            ),
            resolver_version=str(raw.get("resolver_version") or RESOLVER_VERSION),
            catalog_status=(str(raw["catalog_status"]) if raw.get("catalog_status") else None),
            confirmed_label=(str(raw["confirmed_label"]) if raw.get("confirmed_label") else None),
            content_sha256=(str(raw["content_sha256"]) if raw.get("content_sha256") else None),
        )

    @property
    def is_secure_match(self) -> bool:
        return bool(
            self.matched_vehicle_id
            and self.resolution_source in SECURE_SOURCES
        )


class VisualCache(Protocol):
    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def set(self, key: str, value: Mapping[str, Any]) -> None: ...


class InMemoryVisualCache:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.hits = 0

    async def get(self, key: str) -> dict[str, Any] | None:
        found = self.store.get(key)
        if found is not None:
            self.hits += 1
        return found

    async def set(self, key: str, value: Mapping[str, Any]) -> None:
        self.store[key] = dict(value)


def cache_key(
    *,
    conversation_id: str,
    sha256: str,
    vision_model: str,
    resolver_version: str = RESOLVER_VERSION,
) -> str:
    return f"sdr:visres:{conversation_id}:{sha256}:{vision_model}:{resolver_version}"


def fingerprints_from_bindings(
    bindings: Sequence[PresentedVehicleBinding | Mapping[str, Any]],
) -> list[FingerprintRecord]:
    out: list[FingerprintRecord] = []
    for item in bindings:
        parsed = (
            item
            if isinstance(item, PresentedVehicleBinding)
            else PresentedVehicleBinding.from_mapping(item)
        )
        if parsed is None:
            continue
        sha = None
        dhash = None
        if isinstance(item, Mapping):
            sha = (str(item.get("content_sha256") or item.get("sha256") or "").strip() or None)
            dhash = parse_dhash(item.get("dhash") or item.get("perceptual_hash"))
        sha = sha or getattr(parsed, "content_sha256", None)
        dhash = dhash if dhash is not None else parse_dhash(getattr(parsed, "dhash", None))
        if not sha and dhash is None:
            continue
        out.append(
            FingerprintRecord(
                vehicle_id=parsed.vehicle_id,
                conversation_id=parsed.conversation_id,
                sha256=sha,
                dhash=dhash,
                url=parsed.media_url,
            )
        )
    return out


def has_singular_interest(text: str | None) -> bool:
    return bool(_DEMONSTRATIVE.search(text or ""))


def is_weak_vehicle_text(value: Any) -> bool:
    if not isinstance(value, str):
        return not value
    text = value.strip()
    if not text:
        return True
    if _WEAK_VEHICLE_TEXT.match(text):
        return True
    if _DEMONSTRATIVE.search(text) and len(text.split()) <= 4:
        return True
    return False


def _from_quoted(
    quoted: VehicleReferenceResolution | None,
) -> VisualVehicleResolution | None:
    if quoted is None or not quoted.vehicle_id:
        return None
    if quoted.reason == RESOLUTION_EXPLICIT_REPLY:
        source = VisualResolutionSource.QUOTED_MESSAGE
        confidence = 1.0
    elif quoted.reason == RESOLUTION_LISTING:
        source = VisualResolutionSource.LISTING_REFERENCE
        confidence = 1.0
    elif quoted.reason == RESOLUTION_UNIQUE_CONTEXT:
        source = VisualResolutionSource.QUOTED_MESSAGE
        confidence = 0.9
    else:
        return None
    return VisualVehicleResolution(
        resolution_source=source,
        confidence=confidence,
        candidate_vehicle_ids=(quoted.vehicle_id,),
        matched_vehicle_id=quoted.vehicle_id,
        vision_attempted=False,
        vision_calls=0,
    )


def _exact_match(
    media: ValidatedMedia,
    records: Sequence[FingerprintRecord],
    conversation_id: str,
) -> VisualVehicleResolution | None:
    hits = [
        r
        for r in records
        if r.in_scope(conversation_id)
        and r.sha256
        and r.sha256 == media.sha256
    ]
    ids = list(dict.fromkeys(r.vehicle_id for r in hits))
    if len(ids) == 1:
        rec = hits[0]
        return VisualVehicleResolution(
            resolution_source=VisualResolutionSource.EXACT_MEDIA,
            confidence=1.0,
            candidate_vehicle_ids=(ids[0],),
            matched_vehicle_id=ids[0],
            catalog_status=rec.status,
            confirmed_label=_label(rec),
        )
    if len(ids) > 1:
        return VisualVehicleResolution(
            resolution_source=VisualResolutionSource.AMBIGUOUS,
            ambiguity_reason="exact_hash_multiple_vehicles",
            candidate_vehicle_ids=tuple(ids),
            confidence=0.4,
        )
    return None


def _perceptual_match(
    media: ValidatedMedia,
    records: Sequence[FingerprintRecord],
    conversation_id: str,
) -> VisualVehicleResolution | None:
    if media.dhash is None:
        return None
    scored: list[tuple[int, FingerprintRecord]] = []
    for rec in records:
        if not rec.in_scope(conversation_id) or rec.dhash is None:
            continue
        scored.append((hamming_distance(media.dhash, rec.dhash), rec))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0])
    best_d, best = scored[0]
    second_d = scored[1][0] if len(scored) > 1 else 64
    margin = second_d - best_d
    if best_d > DHASH_MAX_DISTANCE:
        return None
    close = [r for d, r in scored if d <= DHASH_MAX_DISTANCE]
    ids = list(dict.fromkeys(r.vehicle_id for r in close))
    if len(ids) > 1 and margin < DHASH_MIN_MARGIN:
        return VisualVehicleResolution(
            resolution_source=VisualResolutionSource.AMBIGUOUS,
            ambiguity_reason="perceptual_margin_insufficient",
            candidate_vehicle_ids=tuple(ids),
            confidence=0.45,
            match_margin=float(margin),
        )
    if len(ids) == 1 and (len(scored) == 1 or margin >= DHASH_MIN_MARGIN):
        return VisualVehicleResolution(
            resolution_source=VisualResolutionSource.PERCEPTUAL_MEDIA,
            confidence=max(0.55, 1.0 - (best_d / 16.0)),
            candidate_vehicle_ids=(ids[0],),
            matched_vehicle_id=ids[0],
            match_margin=float(margin),
            catalog_status=best.status,
            confirmed_label=_label(best),
        )
    if len(ids) > 1:
        return VisualVehicleResolution(
            resolution_source=VisualResolutionSource.AMBIGUOUS,
            ambiguity_reason="perceptual_multiple_vehicles",
            candidate_vehicle_ids=tuple(ids),
            confidence=0.4,
            match_margin=float(margin),
        )
    return None


def _label(rec: FingerprintRecord) -> str | None:
    parts = [p for p in (rec.brand, rec.model) if p]
    return " ".join(parts) if parts else None


def _sanitize_overlay(text: str | None) -> tuple[str | None, bool]:
    if not text:
        return None, False
    adversarial = bool(_INJECTION.search(text))
    cleaned = _INJECTION.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned or None), adversarial


def attributes_from_vision_payload(raw: Mapping[str, Any] | None) -> ObservedAttributes:
    if not isinstance(raw, Mapping):
        return ObservedAttributes()
    overlay, adversarial = _sanitize_overlay(
        str(raw.get("overlay_text") or raw.get("visible_text") or "") or None
    )
    if adversarial is False and _INJECTION.search(str(raw.get("brand") or "")):
        adversarial = True
    year = raw.get("year")
    try:
        year_i = int(year) if year not in (None, "", "null") else None
    except (TypeError, ValueError):
        year_i = None
    conf = float(raw.get("confidence") or 0)
    is_vehicle = raw.get("is_vehicle")
    return ObservedAttributes(
        is_vehicle=bool(is_vehicle) if is_vehicle is not None else None,
        brand=(str(raw["brand"]).strip() if raw.get("brand") else None),
        model=(str(raw["model"]).strip() if raw.get("model") else None),
        color=(str(raw["color"]).strip() if raw.get("color") else None),
        vehicle_type=(str(raw["vehicle_type"]).strip() if raw.get("vehicle_type") else None),
        year=year_i,
        overlay_text=overlay,
        listing_screenshot=bool(raw.get("listing_screenshot") or raw.get("is_listing_screenshot")),
        confidence=conf,
        adversarial=adversarial or bool(raw.get("adversarial")),
    )


async def resolve_visual_vehicle(
    *,
    conversation_id: str,
    quoted: VehicleReferenceResolution | None = None,
    inbound_text: str = "",
    fingerprints: Sequence[FingerprintRecord] = (),
    media: ValidatedMedia | None = None,
    image_bytes: bytes | None = None,
    declared_mime: str | None = None,
    vision: Callable[[bytes, str | None], Awaitable[Mapping[str, Any] | None]] | None = None,
    candidate_lookup: Callable[[ObservedAttributes], Awaitable[Sequence[InventoryCandidate]]] | None = None,
    cache: VisualCache | None = None,
    vision_model: str = "gpt-4o",
    allow_vision: bool = True,
) -> VisualVehicleResolution:
    """Run the resolution hierarchy. Vision is last and never picks an id itself."""
    started = time.monotonic()

    def _stamp(result: VisualVehicleResolution) -> VisualVehicleResolution:
        result.latency_ms = (time.monotonic() - started) * 1000
        if media is not None:
            result.content_sha256 = media.sha256
        return result

    quoted_hit = _from_quoted(quoted)
    has_media = media is not None or image_bytes is not None
    if quoted_hit is not None and quoted is not None:
        # Image bytes take precedence over unique-context inference.
        if quoted.reason in (RESOLUTION_EXPLICIT_REPLY, RESOLUTION_LISTING):
            return _stamp(quoted_hit)
        if quoted.reason == RESOLUTION_UNIQUE_CONTEXT and not has_media:
            return _stamp(quoted_hit)

    if image_bytes is not None and media is None:
        safety = validate_image_bytes(image_bytes, declared_mime=declared_mime)
        if not safety.ok:
            return _stamp(
                VisualVehicleResolution(
                    resolution_source=VisualResolutionSource.UNRESOLVED,
                    fallback_reason=safety.reason,
                )
            )
        from sdr.domain.image_fingerprint import dhash64

        media = ValidatedMedia(
            sha256=sha256_hex(image_bytes),
            dhash=dhash64(image_bytes),
            mime_type=safety.mime_type,
            byte_size=len(image_bytes),
            safety=safety,
        )

    if media is not None:
        exact = _exact_match(media, fingerprints, conversation_id)
        if exact is not None:
            return _stamp(exact)
        perceptual = _perceptual_match(media, fingerprints, conversation_id)
        if perceptual is not None:
            return _stamp(perceptual)

    if not allow_vision or vision is None or image_bytes is None or media is None:
        reason = "vision_not_attempted"
        if media is None and image_bytes is None:
            reason = "no_media"
        return _stamp(
            VisualVehicleResolution(
                resolution_source=VisualResolutionSource.UNRESOLVED,
                fallback_reason=reason,
            )
        )

    ck = cache_key(
        conversation_id=conversation_id,
        sha256=media.sha256,
        vision_model=vision_model,
    )
    if cache is not None:
        cached = await cache.get(ck)
        if isinstance(cached, Mapping) and cached.get("resolution_source"):
            parsed = VisualVehicleResolution.from_mapping(cached)
            parsed.vision_calls = 0
            parsed.vision_attempted = bool(cached.get("vision_attempted"))
            return _stamp(parsed)

    payload = None
    try:
        payload = await vision(image_bytes, media.mime_type)
    except Exception:
        logger.exception("visual vision call failed")
        return _stamp(
            VisualVehicleResolution(
                resolution_source=VisualResolutionSource.UNRESOLVED,
                fallback_reason="vision_failed",
                vision_attempted=True,
                vision_model=vision_model,
                vision_calls=1,
            )
        )

    attrs = attributes_from_vision_payload(payload if isinstance(payload, Mapping) else None)
    if attrs.adversarial:
        # Overlay instructions are data, never control.
        pass
    if attrs.is_vehicle is False:
        result = VisualVehicleResolution(
            resolution_source=VisualResolutionSource.UNRESOLVED,
            observed_attributes=attrs.as_dict(),
            fallback_reason="no_vehicle_in_image",
            vision_attempted=True,
            vision_model=vision_model,
            vision_calls=1,
            confidence=float(attrs.confidence or 0),
        )
        if cache is not None:
            await cache.set(ck, result.to_dict())
        return _stamp(result)

    if not attrs.searchable():
        result = VisualVehicleResolution(
            resolution_source=VisualResolutionSource.ATTRIBUTES_ONLY,
            observed_attributes=attrs.as_dict(),
            fallback_reason="attributes_insufficient",
            vision_attempted=True,
            vision_model=vision_model,
            vision_calls=1,
            confidence=float(attrs.confidence or 0),
        )
        if cache is not None:
            await cache.set(ck, result.to_dict())
        return _stamp(result)

    candidates: list[InventoryCandidate] = []
    if candidate_lookup is not None:
        try:
            found = await candidate_lookup(attrs)
            candidates = [c for c in found if c.vehicle_id]
        except Exception:
            logger.exception("visual candidate lookup failed")
            return _stamp(
                VisualVehicleResolution(
                    resolution_source=VisualResolutionSource.UNRESOLVED,
                    observed_attributes=attrs.as_dict(),
                    fallback_reason="lookup_failed",
                    vision_attempted=True,
                    vision_model=vision_model,
                    vision_calls=1,
                )
            )

    ids = list(dict.fromkeys(c.vehicle_id for c in candidates))
    published = [c for c in candidates if (c.status or "PUBLISHED").upper() == "PUBLISHED"]
    published_ids = list(dict.fromkeys(c.vehicle_id for c in published))

    if len(published_ids) == 1:
        only = next(c for c in published if c.vehicle_id == published_ids[0])
        result = VisualVehicleResolution(
            resolution_source=VisualResolutionSource.VISION_INVENTORY_MATCH,
            confidence=min(0.95, max(0.6, attrs.confidence)),
            candidate_vehicle_ids=(only.vehicle_id,),
            matched_vehicle_id=only.vehicle_id,
            observed_attributes=attrs.as_dict(),
            vision_attempted=True,
            vision_model=vision_model,
            vision_calls=1,
            catalog_status=only.status,
            confirmed_label=" ".join(p for p in (only.brand, only.model) if p) or only.title,
        )
    elif len(ids) > 1 or len(published_ids) > 1:
        result = VisualVehicleResolution(
            resolution_source=VisualResolutionSource.AMBIGUOUS,
            ambiguity_reason="multiple_inventory_candidates",
            candidate_vehicle_ids=tuple(published_ids or ids),
            observed_attributes=attrs.as_dict(),
            vision_attempted=True,
            vision_model=vision_model,
            vision_calls=1,
            confidence=0.4,
        )
    elif len(ids) == 1:
        only = candidates[0]
        result = VisualVehicleResolution(
            resolution_source=VisualResolutionSource.VISION_INVENTORY_MATCH,
            confidence=min(0.9, max(0.55, attrs.confidence)),
            candidate_vehicle_ids=(only.vehicle_id,),
            matched_vehicle_id=only.vehicle_id,
            observed_attributes=attrs.as_dict(),
            vision_attempted=True,
            vision_model=vision_model,
            vision_calls=1,
            catalog_status=only.status,
            confirmed_label=" ".join(p for p in (only.brand, only.model) if p) or only.title,
        )
    else:
        result = VisualVehicleResolution(
            resolution_source=VisualResolutionSource.UNRESOLVED,
            observed_attributes=attrs.as_dict(),
            fallback_reason="no_inventory_match",
            vision_attempted=True,
            vision_model=vision_model,
            vision_calls=1,
            confidence=float(attrs.confidence or 0),
        )

    if cache is not None:
        await cache.set(ck, result.to_dict())
    _ = inbound_text
    return _stamp(result)


def visual_search_override(
    state: ConversationCanonicalState,
) -> tuple[bool, str | None, str] | None:
    """If visual resolution already settled the turn, skip catalog search.

    Returns (block_search, ask_field, reason_code) or None to keep the default path.
    A known textual model is never re-asked because vision failed.
    """
    vis = VisualVehicleResolution.from_mapping(getattr(state, "last_visual_resolution", None))
    if not getattr(state, "visual_applied_this_turn", False):
        return None
    if vis.is_secure_match:
        return None
    facts = getattr(state, "facts", None) or {}
    known_model = (
        bool(facts.get("desired_model"))
        and not is_weak_vehicle_text(facts.get("desired_model"))
    ) or (
        bool(facts.get("desired_vehicle_text"))
        and not is_weak_vehicle_text(facts.get("desired_vehicle_text"))
    )
    if vis.resolution_source is VisualResolutionSource.AMBIGUOUS:
        return (True, None, "visual_ambiguous")
    if vis.fallback_reason == "no_vehicle_in_image":
        if known_model:
            return None
        return (True, "desired_model", "visual_no_vehicle")
    if vis.resolution_source in (
        VisualResolutionSource.UNRESOLVED,
        VisualResolutionSource.ATTRIBUTES_ONLY,
    ) and vis.vision_attempted:
        if known_model:
            return None
        return (True, "desired_model", "visual_unresolved")
    return None


def apply_visual_resolution(
    state: ConversationCanonicalState,
    resolution: VisualVehicleResolution,
    *,
    inbound_text: str = "",
    inbound_timestamp: float | None = None,
) -> None:
    """Fold a visual result into canonical state. Never invent cadastral fields."""
    state.last_visual_resolution = resolution.to_dict()
    state.visual_applied_this_turn = True
    observed = dict(resolution.observed_attributes or {})
    if observed:
        state.facts = {
            **state.facts,
            "observed_visual": observed,
        }
    if observed.get("is_vehicle") is False:
        for key in ("desired_model", "desired_vehicle_text"):
            if is_weak_vehicle_text(state.facts.get(key)):
                next_facts = dict(state.facts)
                next_facts.pop(key, None)
                state.facts = next_facts
        return

    if resolution.resolution_source is VisualResolutionSource.AMBIGUOUS:
        state.facts = {
            **state.facts,
            "visual_match_secure": False,
            "visual_ambiguity": resolution.ambiguity_reason,
        }
        return

    if not resolution.is_secure_match:
        # Observed attributes only — never promote color-only to desired_vehicle.
        return

    vehicle_id = resolution.matched_vehicle_id
    assert vehicle_id
    apply_primary_vehicle_choice(
        state,
        VehicleReferenceResolution(
            vehicle_id=vehicle_id,
            reason=RESOLUTION_EXPLICIT_REPLY
            if resolution.resolution_source
            in (
                VisualResolutionSource.QUOTED_MESSAGE,
                VisualResolutionSource.LISTING_REFERENCE,
                VisualResolutionSource.EXACT_MEDIA,
                VisualResolutionSource.PERCEPTUAL_MEDIA,
                VisualResolutionSource.VISION_INVENTORY_MATCH,
            )
            else RESOLUTION_NONE,
            occurred_at=inbound_timestamp,
        ),
    )
    patch = {
        "visual_match_secure": True,
        "visual_match_vehicle_id": vehicle_id,
        "visual_resolution_source": resolution.resolution_source.value,
    }
    if resolution.confirmed_label and is_weak_vehicle_text(state.facts.get("desired_vehicle_text")):
        patch["desired_vehicle_text"] = resolution.confirmed_label
    if resolution.confirmed_label and is_weak_vehicle_text(state.facts.get("desired_model")):
        # Use the last token as model only when label is "Brand Model".
        tokens = resolution.confirmed_label.split()
        patch["desired_model"] = tokens[-1] if tokens else resolution.confirmed_label
    if resolution.catalog_status:
        patch["matched_catalog_status"] = resolution.catalog_status
    state.facts = {**state.facts, **patch}
    _ = inbound_text


def availability_status_for(
    *,
    resolution: VisualVehicleResolution | None,
    inventory_outcome: str | None,
    inventory_count: int = 0,
    catalog_status: str | None = None,
) -> str:
    """Canonical availability token for the Composer — not a copy template."""
    status = (catalog_status or (resolution.catalog_status if resolution else None) or "").upper()
    if resolution and resolution.resolution_source is VisualResolutionSource.AMBIGUOUS:
        return "ambiguous"
    if status == "SOLD":
        return "sold"
    if status == "RESERVED":
        return "reserved"
    if status in {"DRAFT", "ARCHIVED"}:
        return "unpublished"
    outcome = (inventory_outcome or "").upper()
    if outcome == "SUCCESS_SOLD":
        return "sold"
    if outcome == "SUCCESS_FOUND" and inventory_count == 1:
        return "available"
    if outcome == "SUCCESS_FOUND" and inventory_count > 1:
        if resolution and resolution.is_secure_match:
            return "available"
        return "ambiguous"
    if outcome == "SUCCESS_EMPTY":
        return "unresolved"
    if resolution and resolution.fallback_reason == "no_vehicle_in_image":
        return "unresolved"
    if resolution and resolution.resolution_source is VisualResolutionSource.UNRESOLVED:
        return "unresolved"
    return "unknown"


def sanitized_visual_trace(resolution: VisualVehicleResolution | Mapping[str, Any]) -> dict[str, Any]:
    data = resolution.to_dict() if isinstance(resolution, VisualVehicleResolution) else dict(resolution)
    observed = dict(data.get("observed_attributes") or {})
    observed.pop("overlay_text", None)
    data["observed_attributes"] = observed
    data.pop("image_bytes", None)
    data.pop("base64", None)
    return data


def media_from_bytes(
    data: bytes,
    *,
    declared_mime: str | None = None,
) -> tuple[ValidatedMedia | None, MediaSafetyResult]:
    from sdr.domain.image_fingerprint import dhash64

    safety = validate_image_bytes(data, declared_mime=declared_mime)
    if not safety.ok:
        return None, safety
    media = ValidatedMedia(
        sha256=sha256_hex(data),
        dhash=dhash64(data),
        mime_type=safety.mime_type,
        byte_size=len(data),
        safety=safety,
    )
    return media, safety
