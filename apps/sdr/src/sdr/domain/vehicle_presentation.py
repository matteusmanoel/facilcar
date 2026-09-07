"""Deterministic vehicle presentation — photos + caption, never a text listing.

Published inventory is shown as WhatsApp images with a factual caption on the
LAST photo of each vehicle, plus a follow-up question. The Composer must not
invent a "Olha o que encontrei" card; identity lives in the caption.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

# WhatsApp flood cap. Cover is always included; extras fill the remainder.
DEFAULT_MAX_PHOTOS = 12


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


_TRANSMISSION_PT = {
    "automatic": "automático",
    "automatico": "automático",
    "auto": "automático",
    "cvt": "CVT",
    "manual": "manual",
    "automated": "automatizado",
}


def _vehicle_title(data: Mapping[str, Any]) -> str:
    title = str(_field(data, "title") or "").strip()
    if title and title.lower() not in {"veículo publicado", "veiculo publicado", "publicado"}:
        return title
    brand = str(_field(data, "brand", "marca") or "").strip()
    model = str(_field(data, "model", "modelo") or "").strip()
    version = str(_field(data, "version", "versao", "versão") or "").strip()
    parts = [p for p in (brand, model, version) if p]
    return " ".join(parts)


def _transmission_label(raw: Any, *, es: bool) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    mapped = _TRANSMISSION_PT.get(text.lower())
    if mapped:
        if es and mapped == "automático":
            return "automático"
        if es and mapped == "manual":
            return "manual"
        return mapped
    if text.lower() in {"automatic", "automatico"}:
        return "automático"
    return text


def format_vehicle_caption(
    vehicle: Any,
    *,
    language: str = "pt-BR",
) -> str:
    """Listing caption from published fields only. Missing fields are omitted."""
    data = _as_mapping(vehicle)
    title = _vehicle_title(data)
    year = _field(data, "yearModel", "year_model", "year")
    price = format_price_brl(_field(data, "priceCash", "price_cash", "price"))
    mileage = _field(data, "mileage")
    color = _field(data, "color")
    version = _field(data, "version")
    engine = _field(data, "engineDisplacementLiters", "engine_displacement_liters")
    transmission = _transmission_label(_field(data, "transmission", "cambio"), es=str(language).lower().startswith("es"))

    header = title or "Veículo"
    if year is not None and str(year) not in header:
        header = f"{header} • {year}"

    es = str(language).lower().startswith("es")
    if es:
        price_label, km_label, color_label = "Precio", "Km", "Color"
        version_label, engine_label, trans_label = "Versión", "Motor", "Cambio"
    else:
        price_label, km_label, color_label = "Preço", "Km", "Cor"
        version_label, engine_label, trans_label = "Versão", "Motor", "Câmbio"

    lines = [f"🚗 *{header}*"]
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


def order_images_cover_last(
    rows: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Cover photo is sent last so it carries the caption. No cover → sortOrder last."""
    if not rows:
        return []
    cover = [r for r in rows if bool(r.get("isCover") or r.get("is_cover"))]
    rest = [r for r in rows if not bool(r.get("isCover") or r.get("is_cover"))]
    if not cover:
        return list(rows)
    return rest + [cover[-1]]


def select_images_for_send(
    rows: Sequence[Mapping[str, Any]],
    *,
    limit: int = DEFAULT_MAX_PHOTOS,
) -> list[Mapping[str, Any]]:
    """Choose the outbound set: cover always included and last.

    A cap of N means up to N-1 non-cover photos plus the cover. Slicing after
    ``order_images_cover_last`` must never drop the cover.
    """
    usable = [r for r in rows if str(r.get("url") or "").strip()]
    if not usable:
        return []
    cover = [r for r in usable if bool(r.get("isCover") or r.get("is_cover"))]
    rest = [r for r in usable if not bool(r.get("isCover") or r.get("is_cover"))]
    rest.sort(key=lambda r: int(r.get("sortOrder") or r.get("sort_order") or 0))
    cap = max(0, int(limit))
    if not cover:
        return list(rest[:cap] if cap else rest)
    extras = rest[: max(0, cap - 1)] if cap else rest
    return extras + [cover[-1]]


def media_items_from_images(
    images: Sequence[Mapping[str, Any]],
    *,
    caption: str,
    vehicle_id: str | None = None,
    limit: int = DEFAULT_MAX_PHOTOS,
) -> list[OutboundMedia]:
    """Build outbound images; caption is attached to the LAST photo only."""
    items: list[OutboundMedia] = []
    rows = select_images_for_send(images, limit=limit)
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
