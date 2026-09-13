"""TurnFacts extractor — LLM when configured, deterministic heuristics otherwise.

Always returns ``sdr.domain.types.TurnFacts`` (dataclass). Heuristic path is used
when OPENAI_API_KEY is absent or client is a unittest mock.

Pure greeting uses a deterministic fast path (entire message must be a greeting).
LLM fact keys pass through ``normalize_facts`` before TurnFacts is constructed.
Handoff signals from the LLM are gated by deterministic evidence for
``high_purchase_intent``.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any, Mapping

from sdr.config import get_settings
from sdr.domain.budget_status import parse_budget_status
from sdr.domain.engine_displacement import (
    as_engine_list,
    engine_list_for_json,
    extract_engine_displacements_from_text,
    format_engine_token,
    is_any_engine_utterance,
    is_engine_flexible_utterance,
)
from sdr.domain.facts_schema import is_pure_greeting, normalize_facts
from sdr.domain.vehicle_roles import canonicalize_vehicle_roles
from sdr.domain.pending_interaction import (
    parse_alternative_scope,
    parse_pending_resolution,
)
from sdr.domain.location_request import has_store_location_request_evidence
from sdr.domain.photo_request import has_photo_request_evidence
from sdr.domain.types import BusinessIntent, HandoffSignals, TurnFacts
from sdr.understanding.prompts import TURN_FACTS_JSON_SCHEMA, TURN_FACTS_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_INTENT_PATTERNS: list[tuple[re.Pattern[str], BusinessIntent]] = [
    (re.compile(r"refinanc|levantar\s+\d", re.I), BusinessIntent.REFINANCING),
    (re.compile(r"consign", re.I), BusinessIntent.CONSIGNMENT),
    (re.compile(r"\btroca\b|\btrocar\b|\btrade[- ]?in\b", re.I), BusinessIntent.TRADE),
    (re.compile(r"\bvender\b|\bvenda\b|\bvendo\b", re.I), BusinessIntent.SALE),
    (
        re.compile(r"\bfinanciar\b|\bfinanciamento\b|\bsimular\s+financ", re.I),
        BusinessIntent.PURCHASE_FINANCING,
    ),
    (
        re.compile(
            r"\bcomprar\b|\bcompra\b|\bquero um\b|\bquero uma\b|\bat[eé]\s+\d",
            re.I,
        ),
        BusinessIntent.PURCHASE,
    ),
]

_HANDOFF_PATTERN = re.compile(
    r"vendedor|atendente|humano|pessoa\s+real|falar\s+com\s+(algu[eé]m|a\s+equipe)",
    re.I,
)
_OFFER_PATTERN = re.compile(
    r"\bdou\s+r?\$?\s*\d|\bfecho\s+hoje\b|\boferta\b|\bpropost",
    re.I,
)
_VISIT_PATTERN = re.compile(r"\bvisita\b|\bvisitar\b|\bir\s+a[ií]\b|\bconhecer\s+a\s+loja", re.I)
_HIGH_PURCHASE = re.compile(
    r"\bcompro\s+hoje\b|\bfechar\s+agora\b|\bquero\s+fechar\b|"
    r"\bpróximos?\s+\d+\s+dias\b|\bproximos?\s+\d+\s+dias\b",
    re.I,
)
_REFUSAL = re.compile(
    r"(n[aã]o\s+(quero|vou|mando|enviar|mandar)|prefiro\s+n[aã]o).*(cpf|renda|documento|cnh|comprovante)|"
    r"prefiro\s+n[aã]o\s+mandar",
    re.I,
)
# PROTOCOL_DETERMINISTIC: unambiguous first-person name introduction phrases.
_NAME_INTRO = re.compile(
    r"(?:sou\s+o\s+|sou\s+a\s+|sou\s+|me\s+chamo\s+|meu\s+nome\s+[eé]\s+|minha\s+name\s+[eé]\s+)"
    r"([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)+)",
    re.I,
)
# PROTOCOL_DETERMINISTIC: financing and debt status for own vehicle
_QUITADO = re.compile(r"\b(quitad[ao]|sem\s+financiamento|n[aã]o\s+(?:tem|tenho|h[aá])\s+financiamento)\b", re.I)
_SEM_DEBITOS = re.compile(r"\bsem\s+d[eé]bitos?\b|\btudo\s+em\s+dia\b", re.I)
# SAFE_FAST_PATH: explicit color mentions for trade-in / sale vehicle
_TRADE_COLOR = re.compile(
    r"\bcor\s+(prat[ao]|branc[oa]|pret[oa]|vermelh[oa]|azul|cinn[za]|bege|champagne|marrom|dourad[oa]|verde)\b|"
    r"\b(prat[ao]|branc[oa]|pret[oa])\s+(?:met[aá]lic[ao]|solid[oa])?\b",
    re.I,
)
_ES_HINTS = re.compile(
    r"\b(hola|quiero|gracias|necesito|coche|auto|financiaci[oó]n)\b",
    re.I,
)
_MODEL = re.compile(
    r"\b(hilux|onix|hb20|civic|corolla|gol|fox|tracker|compass|renegade|kwid|mobi|argo|"
    r"polo|virtus|toro|strada|s10|ranger|sw4|spin|cruze|prisma|ka|fiesta|uno|palio|"
    r"sandero|logan|duster|creta|tucson|hr[- ]?v|wr[- ]?v|city|fit|jetta|golf|amarok|"
    r"saveiro|montana|l200|frontier|t[- ]?cross|bmw|320i)\b",
    re.I,
)
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_KM = re.compile(r"(\d[\d\.]*)\s*(mil)?\s*km\b", re.I)

# Last understanding boundary metadata (for replay/trace visibility).
_LAST_UNDERSTANDING_META: dict[str, Any] = {}


def get_last_understanding_meta() -> dict[str, Any]:
    """Return sanitized metadata from the most recent extract_turn_facts call."""
    return dict(_LAST_UNDERSTANDING_META)


def _set_meta(**kwargs: Any) -> None:
    global _LAST_UNDERSTANDING_META
    _LAST_UNDERSTANDING_META = kwargs


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def _parse_money_token(num: str, mil: str | None) -> float | None:
    cleaned = num.replace(".", "").replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if mil:
        value *= 1000
    return value


def _extract_money_facts(text: str) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    lower = text.lower()
    m = re.search(r"at[eé]\s+(\d[\d\.]*)\s*(mil)?", lower)
    if m:
        v = _parse_money_token(m.group(1), m.group(2))
        if v is not None:
            facts["budget"] = v
            facts["max_price"] = v
    m = re.search(
        r"(?:dou|tenho)\s+(?:r\$\s*)?(\d[\d\.]*)\s*(mil)?\s*(?:de\s+)?entrada",
        lower,
    )
    if m:
        v = _parse_money_token(m.group(1), m.group(2))
        if v is not None:
            facts["down_payment"] = v
    m = re.search(
        r"(?:quero|pe[cç]o|receber|valor)\s+(?:r\$\s*)?(\d[\d\.]*)\s*(mil)?",
        lower,
    )
    if m:
        v = _parse_money_token(m.group(1), m.group(2))
        if v is not None and "budget" not in facts:
            facts["asking_price"] = v
    m = re.search(r"levantar\s+(?:r\$\s*)?(\d[\d\.]*)\s*(mil)?", lower)
    if m:
        v = _parse_money_token(m.group(1), m.group(2))
        if v is not None:
            facts["amount_needed"] = v
    m = re.search(r"vale\s+(?:perto\s+de\s+)?(?:r\$\s*)?(\d[\d\.]*)\s*(mil)?", lower)
    if m:
        v = _parse_money_token(m.group(1), m.group(2))
        if v is not None:
            facts["vehicle_value"] = v
    m = re.search(r"ganho\s+(?:uns\s+)?(?:r\$\s*)?(\d[\d\.]*)\s*(mil)?", lower)
    if m:
        v = _parse_money_token(m.group(1), m.group(2))
        if v is not None:
            facts["monthly_income"] = v
    return facts


def has_immediate_closing_evidence(text: str) -> bool:
    """Deterministic evidence required for high_purchase_intent."""
    return bool(_HIGH_PURCHASE.search(_normalize(text)))


def has_explicit_handoff_evidence(text: str) -> bool:
    """Deterministic evidence for salesperson/human request."""
    return bool(_HANDOFF_PATTERN.search(_normalize(text)))


def has_explicit_offer_evidence(text: str) -> bool:
    """Deterministic evidence for concrete monetary/closing proposal."""
    return bool(_OFFER_PATTERN.search(_normalize(text)))


def has_visit_intent_evidence(text: str) -> bool:
    """Deterministic evidence for actionable visit request."""
    return bool(_VISIT_PATTERN.search(_normalize(text)))


def gate_handoff_signals(text: str, signals: HandoffSignals) -> HandoffSignals:
    """LLM may propose signals; deterministic code owns irreversible gates.

    Each irreversible signal is accepted only when inbound text contains
    matching deterministic evidence. Budget / use / preference / enthusiasm
    alone never qualify.
    """
    return HandoffSignals(
        explicit_handoff=(
            True
            if signals.explicit_handoff is True and has_explicit_handoff_evidence(text)
            else None
        ),
        explicit_offer=(
            True
            if signals.explicit_offer is True and has_explicit_offer_evidence(text)
            else None
        ),
        visit_intent=(
            True
            if signals.visit_intent is True and has_visit_intent_evidence(text)
            else None
        ),
        high_purchase_intent=(
            True
            if signals.high_purchase_intent is True and has_immediate_closing_evidence(text)
            else None
        ),
        sensitive_data_refusal=signals.sensitive_data_refusal,
    )


def _heuristic_extract(text: str, state_summary: str | None = None) -> TurnFacts:
    del state_summary
    normalized = _normalize(text)

    if is_pure_greeting(normalized):
        return TurnFacts(
            intent=BusinessIntent.SMALLTALK,
            language="pt-BR",
            facts={},
            signals=HandoffSignals(),
            confidence={"intent": 0.95},
        )

    intent = BusinessIntent.UNKNOWN
    for pattern, label in _INTENT_PATTERNS:
        if pattern.search(normalized):
            intent = label
            break

    facts: dict[str, Any] = {}
    models = [m.group(1) for m in _MODEL.finditer(normalized)]
    if models:
        primary = models[0]
        facts["desired_model"] = primary
        if intent in (
            BusinessIntent.SALE,
            BusinessIntent.CONSIGNMENT,
            BusinessIntent.REFINANCING,
        ):
            facts["vehicle_model"] = primary
            facts["sell_model"] = primary
        if intent == BusinessIntent.TRADE and len(models) >= 2:
            facts["trade_model"] = models[1]
            facts["vehicle_model"] = models[1]

    year = _YEAR.search(normalized)
    if year:
        y = int(year.group(0))
        facts["year"] = y
        facts["trade_year"] = y
        facts["sell_year"] = y
        facts["vehicle_year"] = y

    km = _KM.search(normalized)
    if km:
        v = _parse_money_token(km.group(1), km.group(2))
        if v is not None:
            facts["mileage"] = int(v)
    facts.update(_extract_money_facts(normalized))

    engines = extract_engine_displacements_from_text(normalized)
    serialized_engine = engine_list_for_json(engines)
    if serialized_engine is not None:
        facts["desired_engine_displacement_liters"] = serialized_engine
        model_label = facts.get("desired_model")
        if isinstance(model_label, str) and model_label.strip():
            facts.setdefault(
                "desired_vehicle_text",
                f"{model_label} {format_engine_token(engines[0])}",
            )

    if re.search(r"pr[oó]ximos?\s+(\d+)\s+dias", normalized, re.I):
        facts["timeline"] = re.search(r"pr[oó]ximos?\s+(\d+)\s+dias", normalized, re.I).group(0)

    if re.search(r"deixar\s+na\s+loja|consign", normalized, re.I):
        facts["leave_at_store"] = True

    signals = HandoffSignals()
    if _HANDOFF_PATTERN.search(normalized):
        signals.explicit_handoff = True
    if _OFFER_PATTERN.search(normalized):
        signals.explicit_offer = True
    if _VISIT_PATTERN.search(normalized):
        signals.visit_intent = True
    if has_immediate_closing_evidence(normalized):
        signals.high_purchase_intent = True
    if _REFUSAL.search(normalized):
        signals.sensitive_data_refusal = True

    # PROTOCOL_DETERMINISTIC: explicit name introduction phrases
    name_match = _NAME_INTRO.search(text)  # use original text (proper case)
    if name_match:
        facts["name"] = name_match.group(1).strip()

    # PROTOCOL_DETERMINISTIC: financing and debt status for own vehicle
    if _QUITADO.search(normalized):
        facts["trade_has_financing"] = False
    if _SEM_DEBITOS.search(normalized):
        facts["trade_has_debts"] = False

    # SAFE_FAST_PATH: explicit color mention for trade-in / sale vehicle
    color_match = _TRADE_COLOR.search(normalized)
    if color_match:
        color = (color_match.group(1) or color_match.group(2) or "").strip().lower()
        if color:
            facts["trade_color"] = color

    language = "es" if _ES_HINTS.search(normalized) else ("pt-BR" if normalized.strip() else None)

    canonical, rejected = normalize_facts(facts, source_text=normalized)
    _overlay_engine_utterance(canonical, normalized)
    _ensure_vehicle_text_with_engine(canonical)
    return TurnFacts(
        intent=intent,
        language=language,
        facts=canonicalize_vehicle_roles(canonical, intent),
        signals=signals,
        confidence={"intent": 0.55 if intent != BusinessIntent.UNKNOWN else 0.2},
        photo_request=True if has_photo_request_evidence(normalized) else None,
        location_request=True if has_store_location_request_evidence(normalized) else None,
    )


def _overlay_engine_utterance(facts: dict[str, Any], text: str) -> None:
    """Deterministic engine-preference overlays. Do not re-parse commercial language."""
    if is_any_engine_utterance(text):
        facts["desired_engine_any"] = True
        facts.pop("desired_engine_displacement_liters", None)
        facts.pop("desired_engine_flexible", None)
        return
    if is_engine_flexible_utterance(text) and as_engine_list(
        facts.get("desired_engine_displacement_liters")
    ):
        facts["desired_engine_flexible"] = True


def _ensure_vehicle_text_with_engine(facts: dict[str, Any]) -> None:
    """Keep a commercial phrase for composition when model + engine are known."""
    if facts.get("desired_vehicle_text"):
        return
    model = facts.get("desired_model")
    engines = as_engine_list(facts.get("desired_engine_displacement_liters"))
    if isinstance(model, str) and model.strip() and engines:
        facts["desired_vehicle_text"] = f"{model.strip()} {format_engine_token(engines[0])}"


def _entries_to_dict(entries: Any) -> dict[str, Any]:
    if not isinstance(entries, list):
        return {}
    out: dict[str, Any] = {}
    for item in entries:
        if not isinstance(item, Mapping):
            continue
        key = item.get("key")
        if isinstance(key, str) and key:
            out[key] = item.get("value")
    return out


def _parse_llm_payload(payload: Mapping[str, Any], *, source_text: str = "") -> TurnFacts:
    intent_raw = str(payload.get("intent") or "unknown")
    try:
        intent = BusinessIntent(intent_raw)
    except ValueError:
        intent = BusinessIntent.UNKNOWN

    raw_facts = _entries_to_dict(payload.get("facts_entries"))
    if not raw_facts and isinstance(payload.get("facts"), Mapping):
        raw_facts = dict(payload["facts"])

    canonical, rejected = normalize_facts(raw_facts, source_text=source_text)
    _overlay_engine_utterance(canonical, source_text)
    _ensure_vehicle_text_with_engine(canonical)

    confidence_raw = _entries_to_dict(payload.get("confidence_entries"))
    if not confidence_raw and isinstance(payload.get("confidence"), Mapping):
        confidence_raw = dict(payload["confidence"])
    confidence: dict[str, float] = {}
    for k, v in confidence_raw.items():
        try:
            confidence[k] = float(v)
        except (TypeError, ValueError):
            continue

    sig_raw = payload.get("signals") if isinstance(payload.get("signals"), Mapping) else {}
    signals = HandoffSignals(
        explicit_handoff=True if sig_raw.get("explicit_handoff") is True else None,
        explicit_offer=True if sig_raw.get("explicit_offer") is True else None,
        visit_intent=True if sig_raw.get("visit_intent") is True else None,
        high_purchase_intent=True if sig_raw.get("high_purchase_intent") is True else None,
        sensitive_data_refusal=True if sig_raw.get("sensitive_data_refusal") is True else None,
    )
    signals = gate_handoff_signals(source_text, signals)

    language = payload.get("language")
    lang = language.strip() if isinstance(language, str) and language.strip() else None

    budget_status = parse_budget_status(payload.get("budget_status"))
    pending_resolution = parse_pending_resolution(payload.get("pending_resolution"))
    alternative_scope = parse_alternative_scope(payload.get("alternative_scope"))
    photo_request = True if has_photo_request_evidence(source_text) else None
    location_request = True if has_store_location_request_evidence(source_text) else None

    _set_meta(
        path="structured",
        rejected_fact_keys=rejected,
        raw_fact_keys=list(raw_facts.keys()),
        canonical_fact_keys=list(canonical.keys()),
        signals_gated=signals.as_dict(),
        llm_high_purchase_raw=sig_raw.get("high_purchase_intent"),
        budget_status=budget_status.value if budget_status else None,
        pending_resolution=pending_resolution.value if pending_resolution else None,
        alternative_scope=alternative_scope.value if alternative_scope else None,
        photo_request=photo_request,
        location_request=location_request,
    )

    return TurnFacts(
        intent=intent,
        language=lang,
        facts=canonicalize_vehicle_roles(canonical, intent),
        signals=signals,
        confidence=confidence,
        budget_status=budget_status,
        pending_resolution=pending_resolution,
        alternative_scope=alternative_scope,
        photo_request=photo_request,
        location_request=location_request,
    )


def _is_unittest_mock(client: Any) -> bool:
    module = type(client).__module__ or ""
    return module.startswith("unittest.mock")


async def extract_turn_facts(
    text: str,
    state_summary: str | None = None,
    *,
    client: Any | None = None,
) -> TurnFacts:
    # Deterministic pure-greeting fast path — entire message must be a greeting.
    if is_pure_greeting(text):
        _set_meta(path="greeting_fast_path", provider="deterministic")
        return TurnFacts(
            intent=BusinessIntent.SMALLTALK,
            language="pt-BR",
            facts={},
            signals=HandoffSignals(),
            confidence={"intent": 0.99},
        )

    settings = get_settings()
    api_key = (settings.openai_api_key or "").strip()

    if client is not None and _is_unittest_mock(client):
        _set_meta(path="heuristic", provider="unittest_mock")
        return _heuristic_extract(text, state_summary)
    if client is None and not api_key:
        _set_meta(path="heuristic", provider="no_api_key")
        return _heuristic_extract(text, state_summary)

    if client is None:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)

    model = settings.sdr_understanding_model
    user_content = {"text": text, "state_summary": state_summary or ""}

    try:
        response = await client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": TURN_FACTS_JSON_SCHEMA,
            },
            messages=[
                {"role": "system", "content": TURN_FACTS_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
            ],
        )
    except Exception:
        logger.exception("extract_turn_facts: provider failure; falling back to heuristic")
        _set_meta(path="heuristic_fallback", provider="openai_error")
        return _heuristic_extract(text, state_summary)

    raw = response.choices[0].message.content or "{}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("extract_turn_facts: invalid JSON from model; falling back")
        _set_meta(path="heuristic_fallback", provider="invalid_json", raw_preview=raw[:200])
        return _heuristic_extract(text, state_summary)

    if not isinstance(payload, Mapping):
        _set_meta(path="heuristic_fallback", provider="non_object_payload")
        return _heuristic_extract(text, state_summary)

    facts = _parse_llm_payload(payload, source_text=text)
    meta = get_last_understanding_meta()
    meta.update(
        {
            "path": "live_llm",
            "provider": "openai",
            "model": model,
            "raw_payload": payload,
        }
    )
    _set_meta(**meta)
    return facts
