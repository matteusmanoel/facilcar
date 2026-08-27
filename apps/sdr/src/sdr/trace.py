"""Structured per-turn trace — enabled with SDR_TRACE=true.

Records every major pipeline boundary for a single turn, emitting sanitized
JSON to the logger at DEBUG level.  Sensitive fields (CPF, base64 documents,
raw tokens) are never logged.

Usage
-----
    from sdr.trace import TurnTracer
    with TurnTracer(thread_id=tid, message_id=mid) as t:
        t.inbound(content_type="TEXT", text="Olá")
        t.media(routed_as="text", result_text="Olá")
        t.understanding(intent="smalltalk", language="pt-BR", facts={})
        t.merge(intent_before="unknown", intent_after="smalltalk")
        t.decision(action="smalltalk", reason_code="greeting_or_chitchat", tool_calls=[])
        t.tools_executed([])
        t.composer_input(action="smalltalk", should_introduce=True)
        t.outbound(["Oi! Sou a Júlia da FacilCar..."])
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger("sdr.trace")

_TRACE_ENABLED: bool | None = None
_SENSITIVE_KEYS = frozenset({"cpf", "birth_date", "birth", "cnpj", "plate", "token", "key"})


def _trace_enabled() -> bool:
    global _TRACE_ENABLED
    if _TRACE_ENABLED is None:
        val = os.environ.get("SDR_TRACE", "").strip().lower()
        _TRACE_ENABLED = val in ("1", "true", "yes")
    return _TRACE_ENABLED


def _sanitize(obj: Any, *, depth: int = 0) -> Any:
    """Recursively sanitize sensitive data.  Truncates large strings."""
    if depth > 5:
        return "..."
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k.lower() in _SENSITIVE_KEYS:
                out[k] = "***"
            elif isinstance(v, bytes) or (isinstance(v, str) and len(v) > 2000):
                out[k] = f"<truncated {len(v) if isinstance(v, str) else len(v)}b>"
            else:
                out[k] = _sanitize(v, depth=depth + 1)
        return out
    if isinstance(obj, list):
        return [_sanitize(i, depth=depth + 1) for i in obj]
    if isinstance(obj, bytes):
        return f"<bytes {len(obj)}>"
    return obj


class TurnTracer:
    """Context manager that accumulates a single-turn trace."""

    def __init__(self, *, thread_id: str, message_id: str) -> None:
        self._thread_id = thread_id
        self._message_id = message_id
        self._started = time.monotonic()
        self._stages: list[dict[str, Any]] = []
        self._enabled = _trace_enabled()

    def __enter__(self) -> "TurnTracer":
        return self

    def __exit__(self, *_: object) -> None:
        if not self._enabled:
            return
        elapsed_ms = int((time.monotonic() - self._started) * 1000)
        trace = {
            "thread_id": self._thread_id,
            "message_id": self._message_id,
            "elapsed_ms": elapsed_ms,
            "stages": self._stages,
        }
        payload = json.dumps(_sanitize(trace), ensure_ascii=False)
        # Emit at INFO so SDR_TRACE is visible without DEBUG logging config.
        logger.info("[SDR_TRACE] %s", payload)
        # Also print when running under a TTY / replay so operators see it.
        print(f"[SDR_TRACE] {payload}", flush=True)

    def _record(self, stage: str, **kwargs: Any) -> None:
        if not self._enabled:
            return
        self._stages.append({"stage": stage, **_sanitize(kwargs)})

    def inbound(
        self,
        *,
        content_type: str,
        text: str | None = None,
        media_mime: str | None = None,
        media_status: str | None = None,
        failure_code: str | None = None,
        from_me: bool = False,
    ) -> None:
        self._record(
            "INBOUND",
            content_type=content_type,
            text_len=len(text) if text else 0,
            has_text=bool(text),
            media_mime=media_mime,
            media_status=media_status or "NONE",
            failure_code=failure_code,
            from_me=from_me,
        )

    def media(
        self,
        *,
        routed_as: str,
        result_text: str | None = None,
        error: str | None = None,
    ) -> None:
        self._record(
            "MEDIA_ENRICHMENT",
            routed_as=routed_as,
            has_result=bool(result_text),
            text_len=len(result_text) if result_text else 0,
            error=error,
        )

    def understanding(
        self,
        *,
        intent: str,
        language: str | None,
        facts_keys: list[str],
        signals: dict[str, Any],
        confidence: dict[str, float],
        path: str = "heuristic",
    ) -> None:
        self._record(
            "UNDERSTANDING",
            path=path,
            intent=intent,
            language=language,
            facts_keys=facts_keys,
            signals=signals,
            confidence=confidence,
        )

    def merge(
        self,
        *,
        intent_before: str,
        intent_after: str,
        lifecycle_before: str,
        lifecycle_after: str,
        facts_count: int,
        pending_interaction_before: str | None = None,
        pending_interaction_after: str | None = None,
        alternative_scope: str | None = None,
        budget_status: str | None = None,
    ) -> None:
        self._record(
            "MERGE",
            intent_before=intent_before,
            intent_after=intent_after,
            lifecycle_before=lifecycle_before,
            lifecycle_after=lifecycle_after,
            facts_count=facts_count,
            pending_interaction_before=pending_interaction_before,
            pending_interaction_after=pending_interaction_after,
            alternative_scope=alternative_scope,
            budget_status=budget_status,
        )

    def decision(
        self,
        *,
        action: str,
        reason_code: str | None,
        tool_calls: list[dict[str, Any]],
        ask_field: str | None = None,
        inventory_search_key: str | None = None,
    ) -> None:
        self._record(
            "DECISION",
            action=action,
            reason_code=reason_code,
            planned_tools=[tc.get("tool") for tc in tool_calls],
            ask_field=ask_field,
            inventory_search_key=inventory_search_key,
        )

    def tools_executed(self, results: list[dict[str, Any]]) -> None:
        inv = next((r for r in results if r.get("tool") == "inventory_search"), None)
        self._record(
            "TOOLS",
            executed=[r.get("tool") for r in results],
            has_results=bool(results),
            inventory_outcome=(inv or {}).get("outcome"),
            inventory_search_params=(inv or {}).get("search_params"),
            inventory_count=(inv or {}).get("count"),
        )

    def composer_input(
        self,
        *,
        action: str,
        should_introduce: bool,
        intent: str,
        has_tool_results: bool,
        conversational_affordance: str | None = None,
        budget_status: str | None = None,
        alternative_scope: str | None = None,
    ) -> None:
        self._record(
            "COMPOSER_INPUT",
            action=action,
            should_introduce=should_introduce,
            intent=intent,
            has_tool_results=has_tool_results,
            conversational_affordance=conversational_affordance,
            budget_status=budget_status,
            alternative_scope=alternative_scope,
        )

    def outbound(self, bubbles: list[str]) -> None:
        self._record(
            "OUTBOUND",
            bubble_count=len(bubbles),
            total_chars=sum(len(b) for b in bubbles),
        )

    def batch(
        self,
        *,
        batch_id: str,
        cutoff: str,
        candidate_ids: list[str],
        included_ids: list[str],
        anchor_message_id: str,
        composed_text: str | None = None,
        segments: list[dict[str, Any]] | None = None,
    ) -> None:
        self._record(
            "BATCH",
            batch_id=batch_id,
            cutoff=cutoff,
            candidate_ids=candidate_ids,
            included_ids=included_ids,
            anchor_message_id=anchor_message_id,
            composed_text_len=len(composed_text) if composed_text else 0,
            composed_preview=(composed_text or "")[:120],
            segments=segments or [],
        )

    def media_actions(self, actions: list[dict[str, Any]]) -> None:
        """Reserved for media-outbound contract (not wired in coalesce delivery)."""
        self._record("MEDIA_ACTIONS", count=len(actions), actions=actions)

    def media_send_results(self, results: list[dict[str, Any]]) -> None:
        self._record("MEDIA_SEND", results=results)


class NoopTracer:
    """Drop-in no-op when tracing is disabled."""

    def __enter__(self) -> "NoopTracer":
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def inbound(self, **_: Any) -> None:  # type: ignore[override]
        pass

    def media(self, **_: Any) -> None:
        pass

    def understanding(self, **_: Any) -> None:
        pass

    def merge(self, **_: Any) -> None:
        pass

    def decision(self, **_: Any) -> None:
        pass

    def tools_executed(self, _: list) -> None:
        pass

    def composer_input(self, **_: Any) -> None:
        pass

    def outbound(self, _: list) -> None:
        pass

    def batch(self, **_: Any) -> None:
        pass

    def media_actions(self, _: list) -> None:
        pass

    def media_send_results(self, _: list) -> None:
        pass


def configure_trace_logging() -> None:
    """Ensure sdr.trace logger emits visibly when SDR_TRACE is enabled."""
    if not _trace_enabled():
        return
    trace_logger = logging.getLogger("sdr.trace")
    if not any(isinstance(h, logging.StreamHandler) for h in trace_logger.handlers):
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        trace_logger.addHandler(handler)
    trace_logger.setLevel(logging.INFO)
    trace_logger.propagate = False


def make_tracer(*, thread_id: str, message_id: str) -> TurnTracer | NoopTracer:
    if _trace_enabled():
        configure_trace_logging()
        return TurnTracer(thread_id=thread_id, message_id=message_id)
    return NoopTracer()


# Auto-configure when module imported under SDR_TRACE.
if _trace_enabled():
    configure_trace_logging()
