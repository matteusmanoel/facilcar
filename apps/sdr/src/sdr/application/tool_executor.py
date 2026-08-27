"""Tool executor — runs planned tools from ActionPlan and returns typed ToolResults.

Inventory results always carry an explicit ``outcome`` from ``InventoryOutcome``.
Error strings are classified; the Composer must never infer stock absence from them.
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

from sdr.domain.inventory_outcome import (
    FAILURE_CATEGORY_RETRYABLE,
    FAILURE_CATEGORY_TERMINAL,
    classify_inventory_error,
    inventory_result,
)
from sdr.domain.types import ActionPlan, ConversationCanonicalState, InventoryOutcome

logger = logging.getLogger(__name__)


async def _run_inventory_search(
    state: ConversationCanonicalState,
    pool: asyncpg.Pool,
) -> dict[str, Any]:
    """Search published inventory using typed InventorySearchRequest."""
    from sdr.domain.inventory_search import build_inventory_search_request
    from sdr.tools.inventory import search_with_request

    req = build_inventory_search_request(
        state.facts,
        alternative_scope=state.alternative_scope,
        budget_status=state.budget_status,
        limit=3,
    )
    search_params = req.as_trace_dict()

    try:
        vehicles = await search_with_request(pool, req)
    except TimeoutError:
        return inventory_result(
            outcome=InventoryOutcome.FAILED_RETRYABLE,
            search_params=search_params,
            failure_category=FAILURE_CATEGORY_RETRYABLE,
            error_code="timeout",
        )
    except Exception as exc:
        logger.exception("inventory_search failed")
        outcome = classify_inventory_error(str(exc))
        return inventory_result(
            outcome=outcome,
            search_params=search_params,
            failure_category=(
                FAILURE_CATEGORY_RETRYABLE
                if outcome == InventoryOutcome.FAILED_RETRYABLE
                else FAILURE_CATEGORY_TERMINAL
            ),
            error_code="provider_error",
        )

    # Malformed / unexpected return type.
    if not isinstance(vehicles, list):
        return inventory_result(
            outcome=InventoryOutcome.FAILED_TERMINAL,
            search_params=search_params,
            failure_category=FAILURE_CATEGORY_TERMINAL,
            error_code="malformed_result",
        )

    vehicle_dicts = [v.to_dict() for v in vehicles]
    if not vehicle_dicts:
        return inventory_result(
            outcome=InventoryOutcome.SUCCESS_EMPTY,
            count=0,
            vehicles=[],
            alternatives=[],
            search_params=search_params,
        )

    engine_requested = any(
        d.get("engineMatch") in ("exact", "unknown", "incompatible") for d in vehicle_dicts
    )
    if engine_requested:
        preferred = [d for d in vehicle_dicts if d.get("engineMatch") != "incompatible"]
        alt_cards = [d for d in vehicle_dicts if d.get("engineMatch") == "incompatible"]
        if not preferred:
            return inventory_result(
                outcome=InventoryOutcome.SUCCESS_EMPTY,
                count=0,
                vehicles=[],
                alternatives=alt_cards[:3],
                search_params=search_params,
            )
        return inventory_result(
            outcome=InventoryOutcome.SUCCESS_FOUND,
            count=len(preferred),
            vehicles=preferred,
            alternatives=(alt_cards or preferred)[:3],
            search_params=search_params,
        )

    return inventory_result(
        outcome=InventoryOutcome.SUCCESS_FOUND,
        count=len(vehicle_dicts),
        vehicles=vehicle_dicts,
        alternatives=vehicle_dicts[:3],
        search_params=search_params,
    )


async def _run_send_location(
    state: ConversationCanonicalState,
    pool: asyncpg.Pool | None,
) -> dict[str, Any]:
    return {
        "tool": "send_location",
        "site_settings": {},
    }


async def _run_register_visit_interest(
    state: ConversationCanonicalState,
    pool: asyncpg.Pool | None,
) -> dict[str, Any]:
    return {
        "tool": "register_visit_interest",
        "registered": True,
    }


_TOOL_REGISTRY: dict[str, Any] = {
    "inventory_search": _run_inventory_search,
    "send_location": _run_send_location,
    "register_visit_interest": _run_register_visit_interest,
}


async def execute_tool_calls(
    plan: ActionPlan,
    state: ConversationCanonicalState,
    pool: asyncpg.Pool | None = None,
) -> list[dict[str, Any]]:
    """Execute all tool_calls from the ActionPlan. Returns typed results.

    Never raises — individual tool failures are recorded as typed outcomes.
    """
    results: list[dict[str, Any]] = []
    for tc in plan.tool_calls:
        tool_name = tc.get("tool") or ""
        fn = _TOOL_REGISTRY.get(tool_name)
        if fn is None:
            logger.warning("execute_tool_calls: unknown tool %r", tool_name)
            if tool_name == "inventory_search":
                results.append(
                    inventory_result(
                        outcome=InventoryOutcome.FAILED_TERMINAL,
                        failure_category=FAILURE_CATEGORY_TERMINAL,
                        error_code="unknown_tool",
                    )
                )
            else:
                results.append({"tool": tool_name, "error": "unknown_tool"})
            continue
        try:
            if tool_name == "inventory_search" and pool is None:
                results.append(
                    inventory_result(
                        outcome=InventoryOutcome.FAILED_RETRYABLE,
                        failure_category=FAILURE_CATEGORY_RETRYABLE,
                        error_code="no_db_pool",
                    )
                )
                continue
            if pool is not None or tool_name in ("send_location", "register_visit_interest"):
                result = await fn(state, pool)
            else:
                results.append({"tool": tool_name, "error": "no_db_pool"})
                continue
            results.append(result)
        except Exception as exc:
            logger.exception("execute_tool_calls: %s failed", tool_name)
            if tool_name == "inventory_search":
                results.append(
                    inventory_result(
                        outcome=classify_inventory_error(str(exc)),
                        failure_category=FAILURE_CATEGORY_RETRYABLE,
                        error_code="provider_error",
                    )
                )
            else:
                results.append({"tool": tool_name, "error": str(exc)})
    return results


def tool_results_to_context(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert tool result list to tool_context for the composer.

    Always includes typed ``inventory_outcome`` when inventory ran.
    """
    from sdr.domain.inventory_outcome import classify_inventory_error, extract_inventory_outcome

    ctx: dict[str, Any] = {}
    for r in results:
        tool = r.get("tool")
        if tool == "inventory_search":
            # Normalize legacy payloads that lack an explicit outcome.
            if not r.get("outcome") and not r.get("status"):
                if r.get("error"):
                    r = {
                        **r,
                        "outcome": classify_inventory_error(str(r["error"])).value,
                        "error_code": r["error"],
                    }
                elif r.get("found") and r.get("vehicles"):
                    r = {**r, "outcome": InventoryOutcome.SUCCESS_FOUND.value}
                else:
                    r = {**r, "outcome": InventoryOutcome.SUCCESS_EMPTY.value}

            outcome = r.get("outcome") or InventoryOutcome.NOT_EXECUTED.value
            ctx["inventory_outcome"] = outcome
            ctx["inventory_count"] = int(r.get("count") or 0)
            ctx["inventory_retryable"] = bool(
                r.get("retryable", outcome == InventoryOutcome.FAILED_RETRYABLE.value)
            )
            if r.get("failure_category"):
                ctx["inventory_failure_category"] = r["failure_category"]
            if r.get("error_code") or r.get("error"):
                ctx["inventory_search_error"] = r.get("error_code") or r.get("error")
            if outcome == InventoryOutcome.SUCCESS_FOUND.value and r.get("vehicles"):
                ctx["offers"] = r["vehicles"]
                ctx["inventory_found"] = True
                ctx["alternatives"] = r.get("alternatives") or r["vehicles"]
            elif outcome == InventoryOutcome.SUCCESS_EMPTY.value:
                ctx["inventory_found"] = False
                ctx["offers"] = []
                ctx["alternatives"] = r.get("alternatives") or []
            else:
                ctx["inventory_found"] = None
                ctx["offers"] = []
            ctx["inventory_search_params"] = r.get("search_params", {})
        elif tool == "send_location":
            ctx["site_settings"] = r.get("site_settings", {})
        elif tool == "register_visit_interest":
            ctx["visit_registered"] = r.get("registered", False)
    return ctx
