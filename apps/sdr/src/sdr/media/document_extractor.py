"""Vision-based document field extraction + CPF conflict helper."""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from sdr.config import get_settings

logger = logging.getLogger(__name__)

DocumentType = Literal["CNH", "CRLV", "INCOME_PROOF", "RESIDENCE_PROOF", "OTHER"]

DOCUMENT_TYPES: frozenset[str] = frozenset(
    {"CNH", "CRLV", "INCOME_PROOF", "RESIDENCE_PROOF", "OTHER"}
)

EXTRACTED_FIELDS = (
    "name", "cpf", "birth_date", "birth_city", "birth_state", "plate", "document_type"
)

DOCUMENT_JSON_SCHEMA: dict[str, Any] = {
    "name": "sdr_document_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": ["string", "null"]},
            "cpf": {"type": ["string", "null"]},
            "birth_date": {"type": ["string", "null"]},
            "birth_city": {"type": ["string", "null"]},
            "birth_state": {"type": ["string", "null"]},
            "plate": {"type": ["string", "null"]},
            "document_type": {
                "type": "string",
                "enum": ["CNH", "CRLV", "INCOME_PROOF", "RESIDENCE_PROOF", "OTHER"],
            },
        },
        "required": [
            "name", "cpf", "birth_date", "birth_city", "birth_state",
            "plate", "document_type",
        ],
    },
}

SYSTEM_PROMPT = """\
Extraia campos estruturados de documento brasileiro (CNH, CRLV, comprovante de renda ou residência).

Regras gerais:
- Retorne JSON conforme o schema. Use null quando o campo não estiver legível.
- Não invente CPF, nome, data de nascimento, placa, cidade ou estado.
- document_type: CNH | CRLV | INCOME_PROOF | RESIDENCE_PROOF | OTHER

CPF (campo "CPF" na CNH):
- Copie os 11 dígitos EXATAMENTE como impressos, sem formatação.
- Verifique cada dígito com atenção: 0 ≠ 6, 1 ≠ 7, 3 ≠ 8, 4 ≠ 9.
- Se não tiver certeza de algum dígito, prefira null a inventar.
- O CPF brasileiro tem dois dígitos verificadores (últimos dois); eles nunca são aleatórios.

DATA DE NASCIMENTO:
- SOMENTE o campo rotulado "DATA DE NASCIMENTO" / "NASCIMENTO" / "DATANASC".
- NÃO use data de emissão, validade, 1ª habilitação ou qualquer outra data do documento.
- Preste atenção especial ao MÊS: 01=Janeiro, 04=Abril, 07=Julho, 10=Outubro.
  Dígitos 0 e 1 no mês são facilmente confundidos por OCR; releia com cuidado.
- Formato obrigatório: DD/MM/AAAA exatamente como impresso.

NATURALIDADE (birth_city / birth_state):
- Campo "LOCAL" / "NATURALIDADE" / "NATURAL DE".
- Formato comum na CNH: "FOZ DO IGUAÇU/PR" ou "FOZ DO IGUAÇU - PR".
- birth_city = nome completo da cidade (ex.: "FOZ DO IGUAÇU"), sem a UF.
- birth_state = SOMENTE a sigla de 2 letras do estado (ex.: "PR").
- Nunca invente UF. Se a naturalidade estiver ilegível, use null.
"""

# Valid Brazilian state codes — reject OCR hallucinations like "PE" for "PR" only
# when we cannot validate; we simply null invalid codes.
_BR_UFS = frozenset(
    {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
        "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
        "SP", "SE", "TO",
    }
)


@dataclass(slots=True)
class ExtractedDocument:
    name: str | None = None
    cpf: str | None = None
    birth_date: str | None = None
    birth_city: str | None = None
    birth_state: str | None = None
    plate: str | None = None
    document_type: DocumentType = "OTHER"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "cpf": self.cpf,
            "birth_date": self.birth_date,
            "birth_city": self.birth_city,
            "birth_state": self.birth_state,
            "plate": self.plate,
            "document_type": self.document_type,
        }


@dataclass(slots=True)
class ConflictCheckResult:
    needs_confirmation: bool
    conflicting_fields: list[str] = field(default_factory=list)
    merged_facts: dict[str, Any] = field(default_factory=dict)
    action: str = "apply"  # apply | ask_confirmation


def _is_unittest_mock(client: Any) -> bool:
    module = type(client).__module__ or ""
    return module.startswith("unittest.mock")


def _digits_only(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\D+", "", str(value))


def _norm_critical(value: Any) -> str:
    if value is None:
        return ""
    return "".join(ch for ch in str(value).strip().lower() if ch.isalnum())


def _cpf_valid_checksum(digits: str) -> bool:
    """Validate Brazilian CPF via the two-digit checksum algorithm.

    Returns False for sequences of all-same digits (e.g., 00000000000) and for
    any 11-digit string that fails the official MOD-11 verification.
    """
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    # First check digit
    total = sum(int(digits[i]) * (10 - i) for i in range(9))
    r1 = 0 if (total % 11) < 2 else 11 - (total % 11)
    if r1 != int(digits[9]):
        return False
    # Second check digit
    total = sum(int(digits[i]) * (11 - i) for i in range(10))
    r2 = 0 if (total % 11) < 2 else 11 - (total % 11)
    return r2 == int(digits[10])


def normalize_cpf(value: Any) -> str | None:
    """Normalize CPF to 11 digits and validate checksum.

    Returns None when the extracted string does not pass checksum verification
    rather than storing a wrong value from OCR misreads.
    """
    digits = _digits_only(value)
    if len(digits) != 11:
        return digits or None
    if not _cpf_valid_checksum(digits):
        return None
    return digits


def check_extraction_conflicts(
    state_facts: Mapping[str, Any] | None,
    extracted: Mapping[str, Any] | ExtractedDocument,
) -> ConflictCheckResult:
    """If state has CPF X and extract Y differs → needs_confirmation, do not overwrite.

    Same rule applies to birth_date and plate (critical identity fields).
    """
    state = dict(state_facts or {})
    if isinstance(extracted, ExtractedDocument):
        incoming = extracted.as_dict()
    else:
        incoming = dict(extracted)

    merged = dict(state)
    conflicts: list[str] = []

    for key in ("cpf", "birth_date", "plate", "name"):
        new_val = incoming.get(key)
        if new_val is None or (isinstance(new_val, str) and not new_val.strip()):
            continue
        prev = state.get(key)
        if prev is None or (isinstance(prev, str) and not str(prev).strip()):
            # Safe to take extracted value when state is empty.
            if key == "cpf":
                merged[key] = normalize_cpf(new_val) or new_val
            else:
                merged[key] = new_val
            continue

        if key == "cpf":
            same = _digits_only(prev) == _digits_only(new_val)
        else:
            same = _norm_critical(prev) == _norm_critical(new_val)

        if same:
            if key == "cpf":
                merged[key] = normalize_cpf(new_val) or prev
            else:
                merged[key] = new_val
            continue

        # Conflict: keep previous, flag confirmation — never silent overwrite.
        conflicts.append(key)

    needs = bool(conflicts)
    return ConflictCheckResult(
        needs_confirmation=needs,
        conflicting_fields=conflicts,
        merged_facts=merged,
        action="ask_confirmation" if needs else "apply",
    )


def normalize_birth_date(value: Any) -> str | None:
    """Normalize birth date to DD/MM/AAAA when parseable; otherwise keep trimmed string."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Already BR format
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
            return f"{day:02d}/{month:02d}/{year}"
        return None
    # ISO AAAA-MM-DD → BR
    m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if m2:
        year, month, day = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
            return f"{day:02d}/{month:02d}/{year}"
        return None
    return None


def normalize_naturalidade(
    city: Any,
    state: Any,
) -> tuple[str | None, str | None]:
    """Split combined naturalidade strings and validate UF against BR codes."""
    city_s = str(city).strip() if isinstance(city, str) and city.strip() else None
    state_s = str(state).strip().upper() if isinstance(state, str) and state.strip() else None

    # Combined forms: "FOZ DO IGUAÇU/PR", "FOZ DO IGUACU - PR", "CIDADE PR"
    if city_s:
        combined = re.match(
            r"^(.+?)\s*[/\-–,]\s*([A-Za-z]{2})$",
            city_s,
        )
        if combined:
            city_s = combined.group(1).strip() or None
            if not state_s:
                state_s = combined.group(2).upper()
        else:
            trailing = re.match(r"^(.+?)\s+([A-Za-z]{2})$", city_s)
            if trailing and trailing.group(2).upper() in _BR_UFS:
                city_s = trailing.group(1).strip() or None
                if not state_s:
                    state_s = trailing.group(2).upper()

    if state_s and state_s not in _BR_UFS:
        state_s = None

    if city_s:
        city_s = re.sub(r"\s+", " ", city_s).strip().upper() or None

    return city_s, state_s


def rasterize_pdf_first_page(data: bytes, *, scale: float = 3.0) -> bytes | None:
    """Render the first PDF page to JPEG. Vision APIs reject application/pdf."""
    if not data:
        return None
    try:
        import pypdfium2 as pdfium
    except ImportError:
        logger.warning("pypdfium2 is required to rasterize PDFs for vision")
        return None
    try:
        pdf = pdfium.PdfDocument(data)
        try:
            if len(pdf) < 1:
                return None
            page = pdf[0]
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")
            buf = io.BytesIO()
            pil_image.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
        finally:
            pdf.close()
    except Exception:
        logger.exception("rasterize_pdf_first_page failed")
        return None


def prepare_vision_payload(
    data: bytes,
    mime_type: str | None,
) -> tuple[bytes, str] | None:
    """Return image bytes + MIME suitable for Vision image_url.

    PDFs are rasterized; other bytes pass through as an image MIME.
    """
    mime = (mime_type or "image/jpeg").lower().split(";", 1)[0].strip()
    looks_pdf = mime in {"application/pdf", "image/pdf"} or mime.endswith("/pdf")
    if looks_pdf or data[:4] == b"%PDF":
        raster = rasterize_pdf_first_page(data)
        if not raster:
            return None
        return raster, "image/jpeg"
    if not mime.startswith("image/"):
        mime = "image/jpeg"
    return data, mime


def _parse_payload(payload: Mapping[str, Any]) -> ExtractedDocument:
    doc_type_raw = str(payload.get("document_type") or "OTHER").upper()
    doc_type: DocumentType
    if doc_type_raw in DOCUMENT_TYPES:
        doc_type = doc_type_raw  # type: ignore[assignment]
    else:
        doc_type = "OTHER"

    name = payload.get("name")
    cpf = normalize_cpf(payload.get("cpf"))
    birth = normalize_birth_date(payload.get("birth_date"))
    birth_city, birth_state = normalize_naturalidade(
        payload.get("birth_city"),
        payload.get("birth_state"),
    )
    plate = payload.get("plate")

    return ExtractedDocument(
        name=str(name).strip() if isinstance(name, str) and name.strip() else None,
        cpf=cpf,
        birth_date=birth,
        birth_city=birth_city,
        birth_state=birth_state,
        plate=str(plate).strip().upper() if isinstance(plate, str) and plate.strip() else None,
        document_type=doc_type,
    )


async def extract_document(
    data: bytes,
    *,
    mime_type: str | None = None,
    state_facts: Mapping[str, Any] | None = None,
    client: Any | None = None,
) -> tuple[ExtractedDocument, ConflictCheckResult]:
    """Extract structured fields from a document image/PDF page via Vision."""
    empty = ExtractedDocument()
    if not data:
        return empty, check_extraction_conflicts(state_facts, empty)

    settings = get_settings()
    api_key = (settings.openai_api_key or "").strip()
    prepared = prepare_vision_payload(data, mime_type)
    if prepared is None:
        logger.warning("extract_document: could not prepare a vision image from %s", mime_type)
        return empty, check_extraction_conflicts(state_facts, empty)
    data, mime = prepared

    if client is None:
        if not api_key:
            logger.warning("extract_document: no OPENAI_API_KEY; returning empty")
            return empty, check_extraction_conflicts(state_facts, empty)
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)

    b64 = base64.b64encode(data).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    model = settings.sdr_vision_model

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Extraia os campos do documento."},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]
    create_kwargs: dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": DOCUMENT_JSON_SCHEMA,
        },
    }

    if _is_unittest_mock(client):
        create = client.chat.completions.create
        response = create(**create_kwargs)
        if hasattr(response, "__await__"):
            response = await response
    else:
        response = await client.chat.completions.create(**create_kwargs)

    raw = "{}"
    try:
        raw = response.choices[0].message.content or "{}"
    except (AttributeError, IndexError, TypeError):
        if isinstance(response, dict):
            raw = json.dumps(response)
        elif isinstance(response, str):
            raw = response

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("extract_document: invalid JSON from model")
        payload = {}

    if not isinstance(payload, Mapping):
        payload = {}

    extracted = _parse_payload(payload)
    conflict = check_extraction_conflicts(state_facts, extracted)
    return extracted, conflict
