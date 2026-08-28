"""Deterministic vehicle presentation — photos + caption, never a text listing.

Published inventory is shown as WhatsApp images with a factual caption on the
LAST photo of each vehicle, plus a follow-up question. The Composer must not
invent a "Olha o que encontrei" card; identity lives in the caption.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

DEFAULT_MAX_PHOTOS = 5


@dataclass(frozen=True, slots=True)
class OutboundMedia:
    """One outbound media item the orchestrator must send (not a text bubble)."""

    mediatype: str
    url: str
    mimetype: str
    caption: str = ""
    vehicle_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mediatype": self.mediatype,
            "url": self.url,
            "mimetype": self.mimetype,
            "caption": self.caption,
            "vehicle_id": self.vehicle_id,
        }


def format_price_brl(value: Any) -> str | None:
    """Format a cash price as Brazilian reais (R$ 84.900). Never invent."""
    if value is None:
        return None
    try:
        number = int(round(float(Decimal(str(value)))))
    except (TypeError, ValueError, ArithmeticError):
        return None
    grouped = f"{number:,}".replace(",", ".")
    return f"R$ {grouped}"


def _mimetype_from_url(url: str) -> str:
    path = url.split("?", 1)[0].lower()
    if path.endswith(".png"):
        return "image/png"
    if path.endswith(".webp"):
        return "image/webp"
    if path.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


def _as_mapping(vehicle: Any) -> Mapping[str, Any]:
    if isinstance(vehicle, Mapping):
        return vehicle
    to_dict = getattr(vehicle, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        if isinstance(data, Mapping):
            return data
    return {}


def _field(vehicle: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in vehicle and vehicle[key] is not None:
            value = vehicle[key]
            if isinstance(value, str) and not value.strip():
                continue
            return value
    return None


def format_vehicle_caption(
    vehicle: Any,
    *,
    language: str = "pt-BR",
) -> str:
    """Listing caption from published fields only. Missing fields are omitted."""
    data = _as_mapping(vehicle)
    title = str(_field(data, "title") or "").strip()
    year = _field(data, "yearModel", "year_model")
    price = format_price_brl(_field(data, "priceCash", "price_cash", "price"))
    mileage = _field(data, "mileage")
    color = _field(data, "color")
    version = _field(data, "version")
    engine = _field(data, "engineDisplacementLiters", "engine_displacement_liters")
    transmission = _field(data, "transmission", "cambio")

    header = title or "Veículo publicado"
    if year is not None and str(year) not in header:
        header = f"{header} • {year}"

    es = str(language).lower().startswith("es")
    if es:
        price_label, km_label, color_label = "Precio", "Km", "Color"
        version_label, engine_label, trans_label = "Versión", "Motor", "Cambio"
    else:
        price_label, km_label, color_label = "Preço", "Km", "Cor"
        version_label, engine_label, trans_label = "Versão", "Motor", "Câmbio"

    lines = [f"🚗 {header}"]
    if price:
        lines.append(f"💰 {price_label}: {price}")
    if mileage is not None:
        try:
            km_int = int(mileage)
            km_txt = f"{km_int:,}".replace(",", ".")
        except (TypeError, ValueError):
            km_txt = str(mileage)
        lines.append(f"📏 {km_label}: {km_txt}")
    if color:
        lines.append(f"🎨 {color_label}: {color}")
    if version:
        lines.append(f"🏷️ {version_label}: {version}")
    if engine is not None:
        lines.append(f"⚙️ {engine_label}: {engine}")
    if transmission:
        lines.append(f"🔧 {trans_label}: {transmission}")
    if es:
        lines.append("Vale la visita para verlo de cerca.")
    else:
        lines.append("Conforto e estilo sem igual.")
    return "\n".join(lines)


def _image_rows(vehicle: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = vehicle.get("images") or []
    if not isinstance(raw, list):
        return []
    rows: list[Mapping[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        rows.append(item)
    rows.sort(key=lambda r: int(r.get("sortOrder") or r.get("sort_order") or 0))
    return rows


def media_items_from_images(
    images: Sequence[Mapping[str, Any]],
    *,
    caption: str,
    vehicle_id: str | None = None,
    limit: int = DEFAULT_MAX_PHOTOS,
) -> list[OutboundMedia]:
    """Build outbound images; caption is attached to the LAST photo only."""
    items: list[OutboundMedia] = []
    rows = [img for img in images if str(img.get("url") or "").strip()]
    rows = rows[: max(0, limit)]
    last_index = len(rows) - 1
    for index, image in enumerate(rows):
        url = str(image.get("url") or "").strip()
        items.append(
            OutboundMedia(
                mediatype="image",
                url=url,
                mimetype=_mimetype_from_url(url),
                caption=caption if index == last_index else "",
                vehicle_id=vehicle_id,
            )
        )
    return items


def media_items_from_vehicles(
    vehicles: Sequence[Any],
    *,
    language: str = "pt-BR",
    max_photos_single: int = DEFAULT_MAX_PHOTOS,
) -> list[OutboundMedia]:
    """One vehicle: up to N photos, caption on last. Several: cover photo each."""
    cards = [_as_mapping(v) for v in vehicles if v is not None]
    cards = [c for c in cards if c]
    if not cards:
        return []
    if len(cards) == 1:
        card = cards[0]
        return media_items_from_images(
            _image_rows(card),
            caption=format_vehicle_caption(card, language=language),
            vehicle_id=str(card.get("id") or "") or None,
            limit=max_photos_single,
        )
    items: list[OutboundMedia] = []
    for card in cards[:3]:
        images = _image_rows(card)
        cover = images[:1]
        items.extend(
            media_items_from_images(
                cover,
                caption=format_vehicle_caption(card, language=language),
                vehicle_id=str(card.get("id") or "") or None,
                limit=1,
            )
        )
    return items


def shown_vehicle_ids(vehicles: Sequence[Any]) -> list[str]:
    ids: list[str] = []
    for vehicle in vehicles:
        data = _as_mapping(vehicle)
        vid = str(data.get("id") or "").strip()
        if vid:
            ids.append(vid)
    return ids
