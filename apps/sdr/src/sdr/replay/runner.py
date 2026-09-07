"""Golden scenario runner used by the replay CLI and by pytest.

Usage (from apps/sdr via uv):
    uv run python -m sdr.replay fox_peugeot_troca
    uv run python -m sdr.replay --all
    uv run python -m sdr.replay --llm-real --all
    uv run python -m sdr.replay --show-trace civic_vendido_foto
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCENARIOS_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "golden" / "scenarios"
_TRANSCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "golden" / "transcripts"


def list_scenarios() -> list[Path]:
    return sorted(_SCENARIOS_DIR.glob("*.json"))


def load_scenario(name_or_path: str) -> dict[str, Any]:
    p = Path(name_or_path)
    if not p.exists():
        candidate = _SCENARIOS_DIR / f"{name_or_path}.json"
        if candidate.exists():
            p = candidate
        else:
            raise FileNotFoundError(f"Scenario not found: {name_or_path!r}")
    return json.loads(p.read_text())


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class ScenarioRunResult:
    ok: bool
    errors: list[str]
    name: str
    turns: list[dict[str, Any]] = field(default_factory=list)
    vendor_summary: str | None = None
    llm_real: bool = False
    final_state: Any = None
    obtained_terminal: str = "INCOMPLETE"
    crm_report: dict[str, Any] | None = None
    fallback_count: int = 0
    retry_count: int = 0
    traces: list[dict[str, Any]] = field(default_factory=list)
    clock_iso: str | None = None
    seed_version: str | None = None
    understanding_model: str | None = None
    composer_model: str | None = None
    technical_status: str = "TECHNICAL_FAIL"
    summary_validation: dict[str, Any] | None = None
    summary_llm_rejected: bool = False
    summary_used_fallback: bool = False
    invariants_executed: list[str] = field(default_factory=list)



# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _initial_state(scenario: dict[str, Any]) -> Any:
    from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState

    name = scenario.get("name", "unknown")
    init = scenario.get("initial_state") or {}
    state = ConversationCanonicalState(
        thread_id=f"replay_{name}",
        customer=CustomerState(phone="5541999999999"),
    )
    for k, v in init.items():
        if not hasattr(state, k):
            continue
        if k == "intent" and isinstance(v, str):
            try:
                v = BusinessIntent(v.lower())
            except ValueError:
                pass
        setattr(state, k, v)
    return state


def _stub_understand(turns: list[dict[str, Any]]):
    from sdr.domain.types import BusinessIntent, ConversationCanonicalState, HandoffSignals, TurnFacts

    understand_stubs: list[dict[str, Any]] = [t.get("understand_return") or {} for t in turns]
    turn_idx_ref: list[int] = [0]

    async def _understand(text: str, st: ConversationCanonicalState) -> TurnFacts:
        idx = turn_idx_ref[0]
        stub = understand_stubs[idx] if idx < len(understand_stubs) else {}
        intent_str = stub.get("intent", "UNKNOWN")
        try:
            intent = BusinessIntent(intent_str.lower())
        except ValueError:
            intent = BusinessIntent.UNKNOWN
        facts = stub.get("facts") or {}
        signals_raw = stub.get("signals") or {}
        if signals_raw:
            valid_fields = {f.name for f in HandoffSignals.__dataclass_fields__.values()}
            signals = HandoffSignals(**{k: v for k, v in signals_raw.items() if k in valid_fields})
        else:
            signals = HandoffSignals()
        return TurnFacts(intent=intent, facts=facts, signals=signals)

    return _understand, turn_idx_ref, understand_stubs


async def run_scenario(
    scenario: dict[str, Any],
    *,
    show_trace: bool = False,
    pool: Any = None,
    llm_real: bool = False,
    use_live_inventory: bool = False,
) -> tuple[bool, list[str]]:
    """Run a golden scenario. Returns (ok, errors).

    ``llm_real=True`` uses the live Understanding + Composer LLMs and resets
    canonical state at the start of the scenario (equivalent to ``/deletar``).
    """
    result = await run_scenario_detailed(
        scenario,
        show_trace=show_trace,
        pool=pool,
        llm_real=llm_real,
        use_live_inventory=use_live_inventory,
    )
    return result.ok, result.errors


async def run_scenario_detailed(
    scenario: dict[str, Any],
    *,
    show_trace: bool = False,
    pool: Any = None,
    llm_real: bool = False,
    use_live_inventory: bool = False,
) -> ScenarioRunResult:
    import contextlib
    import time
    import unittest.mock as mock

    from sdr.application.process_turn import process_turn
    from sdr.domain.clock import GOLDEN_CLOCK_ISO, set_clock
    from sdr.domain.inbound import ContentType, InboundTurn, MediaStatus
    from sdr.domain.types import Action
    from sdr.infrastructure.isolated_crm import IsolatedCrmStore
    from tests.golden.fixtures.seed_inventory_adapter import SEED_VERSION
    from tests.golden.invariants import INVARIANT_CATALOG, check_scenario, check_turn

    name = scenario.get("name", "unknown")
    turns = scenario.get("turns", [])
    state = _initial_state(scenario)
    errors: list[str] = []
    transcript: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    vendor_summary: str | None = None
    fallback_count = 0
    crm_store = IsolatedCrmStore()
    crm_report: dict[str, Any] | None = None
    summary_validation: dict[str, Any] | None = None
    summary_llm_rejected = False
    summary_used_fallback = False
    clock_iso = scenario.get("clock") or GOLDEN_CLOCK_ISO
    set_clock(clock_iso)

    async def _seed_run_inventory_search(search_state: Any, _pool: Any) -> dict[str, Any]:
        from sdr.domain.inventory_outcome import inventory_result
        from sdr.domain.inventory_search import build_inventory_search_request
        from sdr.domain.types import InventoryOutcome
        from tests.golden.fixtures.seed_inventory_adapter import search_seed

        req = build_inventory_search_request(
            search_state.facts,
            alternative_scope=search_state.alternative_scope,
            budget_status=search_state.budget_status,
            limit=3,
        )
        model = getattr(req, "original_model", None) or ""
        brand = getattr(req, "original_brand", None) or ""
        listing_id = getattr(search_state, "listing_reference", None) or search_state.facts.get(
            "_seed_vehicle_hint"
        )
        listing_url = None
        if isinstance(listing_id, str) and listing_id.startswith("http"):
            listing_url, listing_id = listing_id, None
        result = search_seed(
            model=model,
            brand=brand,
            vehicle_hint_id=listing_id,
            listing_url=listing_url,
        )
        outcome_str = result.get("outcome", "SUCCESS_EMPTY")
        search_params = req.as_trace_dict() if hasattr(req, "as_trace_dict") else {}
        listing_meta = {
            "listing_reference_received": result.get("listing_reference_received"),
            "listing_reference_resolved": result.get("listing_reference_resolved"),
            "matched_inventory_id": result.get("matched_inventory_id"),
            "matched_status": result.get("matched_status"),
            "inventory_outcome": result.get("inventory_outcome") or outcome_str,
        }
        if outcome_str == "SUCCESS_FOUND":
            vehicles = result.get("vehicles") or []
            payload = inventory_result(
                outcome=InventoryOutcome.SUCCESS_FOUND,
                count=len(vehicles),
                vehicles=vehicles,
                alternatives=vehicles[:3],
                search_params=search_params,
            )
        elif outcome_str == "SUCCESS_SOLD":
            vehicle = result.get("vehicle") or {}
            payload = inventory_result(
                outcome=InventoryOutcome.SUCCESS_SOLD,
                count=0,
                vehicles=[vehicle],
                alternatives=[],
                search_params=search_params,
            )
            payload["listing_id"] = result.get("listing_id")
        else:
            payload = inventory_result(
                outcome=InventoryOutcome.SUCCESS_EMPTY,
                count=0,
                vehicles=[],
                alternatives=[],
                search_params=search_params,
            )
        payload.update(listing_meta)
        return payload

    if llm_real:
        from sdr.orchestrator import default_understand

        understand = default_understand
        turn_idx_ref = [0]
        understand_stubs: list[dict[str, Any]] = []
    else:
        understand, turn_idx_ref, understand_stubs = _stub_understand(turns)

    process_pool = pool if pool is not None else object()
    understanding_model = None
    composer_model = None
    if llm_real:
        from sdr.config import get_settings

        settings = get_settings()
        understanding_model = getattr(settings, "openai_model", None) or "gpt-4.1-mini"
        composer_model = getattr(settings, "openai_composer_model", None) or understanding_model

    for idx, turn_def in enumerate(turns):
        turn_idx_ref[0] = idx
        inbound_text = turn_def.get("inbound", "")
        listing_id = turn_def.get("listing_id")
        listing_url = turn_def.get("listing_url")
        state_before = {
            "intent": state.intent.value if hasattr(state.intent, "value") else str(state.intent),
            "facts": dict(state.facts),
            "missing_fields": list(state.missing_fields or []),
            "deferred_fields": list(state.deferred_fields or []),
            "collected_fields": list(state.collected_fields or []),
            "visit_preferred_time": state.visit_preferred_time,
        }
        inbound = InboundTurn(
            thread_id=state.thread_id,
            content_type=ContentType.TEXT,
            text=inbound_text,
            media_status=MediaStatus.NONE,
            raw_message_ref={
                k: v
                for k, v in {
                    "listing_id": listing_id,
                    "listing_url": listing_url,
                    "media_metadata": turn_def.get("media_metadata"),
                }.items()
                if v
            },
        )
        if show_trace:
            print(f"\n{'='*60}")
            print(f"  Turn {idx}: {inbound_text!r}")
            print(f"  listing_id: {listing_id}")
            print(f"  assistant_turn_count: {state.assistant_turn_count}")
            print(f"  State facts before: {dict(state.facts)}")

        started = time.perf_counter()
        try:
            ctx = (
                mock.patch.dict(
                    "sdr.application.tool_executor._TOOL_REGISTRY",
                    {"inventory_search": _seed_run_inventory_search},
                )
                if not use_live_inventory
                else contextlib.nullcontext()
            )
            with ctx:
                result = await process_turn(
                    state=state,
                    inbound=inbound,
                    inbound_text=inbound_text,
                    understand=understand,
                    pool=process_pool,
                )
        except Exception as exc:
            errors.append(f"[{name}] turn {idx}: process_turn raised {type(exc).__name__}: {exc}")
            break
        latency_ms = int((time.perf_counter() - started) * 1000)

        plan = result.action_plan
        action_val = plan.action.value if hasattr(plan.action, "value") else str(plan.action)
        facts_out = {
            k: v for k, v in result.turn_facts.facts.items() if v is not None
        } if result.turn_facts else {}
        inv_tr = next(
            (tr for tr in (result.tool_results or []) if tr.get("tool") == "inventory_search"),
            {},
        )
        validator = result.validator_result or {}
        fallback_used = bool(validator.get("fallback_used"))
        if fallback_used:
            fallback_count += 1
        if not (result.outbound_texts or []) and action_val != "NO_REPLY":
            errors.append(f"[{name}] turn {idx}: empty Composer outbound")

        from sdr.domain.vehicle_presentation import vehicle_card_record

        vehicle_cards = []
        if action_val.upper() == "SHOW_OFFERS" and (inv_tr.get("outcome") == "SUCCESS_FOUND"):
            for veh in inv_tr.get("vehicles") or []:
                vehicle_cards.append(vehicle_card_record(veh))
        media_items = []
        for item in getattr(result, "outbound_media", None) or []:
            media_items.append(
                item.to_dict() if hasattr(item, "to_dict") else {
                    "caption": getattr(item, "caption", None),
                    "url": getattr(item, "url", None),
                    "vehicle_id": getattr(item, "vehicle_id", None),
                    "mediatype": getattr(item, "mediatype", None),
                }
            )

        transcript.append({
            "idx": idx,
            "inbound": inbound_text,
            "intent": result.turn_facts.intent.value if result.turn_facts else None,
            "facts_extracted": facts_out,
            "action": action_val,
            "ask_field": plan.ask_field,
            "should_introduce": (
                result.response_directive.should_introduce
                if result.response_directive
                else None
            ),
            "outbound": list(result.outbound_texts or []),
            "vehicle_cards": vehicle_cards,
            "outbound_media": media_items,
            "inventory_outcome": inv_tr.get("outcome"),
            "inventory_query_model": (inv_tr.get("search_params") or {}).get("original_model"),
            "listing_reference_received": inv_tr.get("listing_reference_received"),
            "listing_reference_resolved": inv_tr.get("listing_reference_resolved"),
            "matched_inventory_id": inv_tr.get("matched_inventory_id"),
        })
        trace_row = {
            "scenario_id": name,
            "turn_id": idx,
            "timestamp": clock_iso,
            "timezone": "America/Sao_Paulo",
            "customer_message": inbound_text,
            "listing_metadata": inbound.raw_message_ref,
            "understanding_model": understanding_model if llm_real else "stub",
            "raw_facts": facts_out,
            "normalized_facts": dict(result.state.facts),
            "extracted_intent": result.turn_facts.intent.value if result.turn_facts else None,
            "final_intent": result.state.intent.value,
            "state_before": state_before,
            "state_after": {
                "intent": result.state.intent.value,
                "facts": dict(result.state.facts),
                "handoff_ready": result.state.handoff_ready,
                "profile_complete": result.state.profile_complete,
                "missing_fields": list(result.state.missing_fields or []),
                "deferred_fields": list(result.state.deferred_fields or []),
                "collected_fields": list(result.state.collected_fields or []),
                "visit_preferred_time": result.state.visit_preferred_time,
                "last_inventory_match": result.state.last_inventory_match,
            },
            "applicable_fields": list(result.state.collected_fields or [])
            + list(result.state.missing_fields or []),
            "missing_fields": list(result.state.missing_fields or []),
            "deferred_fields": list(result.state.deferred_fields or []),
            "action_plan": {
                "action": action_val,
                "reason_code": plan.reason_code,
                "handoff": plan.handoff,
            },
            "ask_field": plan.ask_field,
            "tool_calls": plan.tool_calls,
            "tool_results": result.tool_results,
            "inventory_query": inv_tr.get("search_params"),
            "inventory_match": result.state.last_inventory_match,
            "composer_result": list(result.outbound_texts or []),
            "vehicle_cards": vehicle_cards,
            "outbound_media": media_items,
            "composer_model": composer_model if llm_real else "template/stub",
            "retry": 0,
            "fallback": fallback_used,
            "validations": validator,
            "latency_ms": latency_ms,
            "handoff_reason": result.state.lifecycle.handoff_reason,
        }
        traces.append(trace_row)
        if show_trace:
            if not llm_real and idx < len(understand_stubs):
                print(f"  Stub understand: intent={understand_stubs[idx].get('intent', 'UNKNOWN')}")
            else:
                print(f"  Understand: intent={result.turn_facts.intent.value} facts={facts_out}")
            print(f"  Action: {action_val}")
            print(f"  ask_field: {plan.ask_field}")
            print(f"  inventory_match: {result.state.last_inventory_match}")
            print(f"  Outbound: {result.outbound_texts}")
            if result.tool_results:
                for tr in result.tool_results:
                    print(f"  ToolResult: {tr.get('tool')} outcome={tr.get('outcome')}")

        turn_for_check = dict(turn_def)
        turn_for_check.pop("llm_real_only", None)
        violations = check_turn(
            scenario_name=name,
            turn_idx=idx,
            turn_def=turn_for_check,
            result=result,
        )
        inv_msgs = [str(v) for v in violations]
        for v in inv_msgs:
            errors.append(v)
        trace_row["invariant_results"] = inv_msgs or ["pass"]

        if plan.action == Action.HANDOFF_VENDOR or plan.handoff:
            from sdr.domain.vendor_summary import compose_vendor_summary

            composed = None
            try:
                composed = compose_vendor_summary(result.state)
                vendor_summary = composed.text
                summary_validation = composed.validation
                summary_llm_rejected = composed.llm_rejected
                summary_used_fallback = composed.used_fallback
            except Exception as exc:
                vendor_summary = f"(summary failed: {exc})"
                summary_validation = {"pass": False, "violations": [str(exc)]}
                summary_llm_rejected = False
                summary_used_fallback = True
            stored = crm_store.persist_handoff(result.state, composed=composed)
            crm_report = crm_store.verify(result.state.thread_id)
            trace_row["crm_payload"] = stored
            trace_row["crm_persist"] = crm_report
            trace_row["summary_validation"] = summary_validation
            if summary_validation and not summary_validation.get("pass"):
                errors.append(
                    f"[{name}] turn {idx}: summary_validation — {summary_validation.get('violations')}"
                )
            if show_trace:
                print(f"  CRM juliaSummary: {vendor_summary}")
                print(f"  CRM persist verified: {crm_report.get('matches_payload')}")
                print(f"  summary_validation: {summary_validation}")

        state = result.state

    expected_final_intent = scenario.get("expected_final_intent")
    if expected_final_intent and turns:
        actual_intent = state.intent.value if hasattr(state.intent, "value") else str(state.intent)
        if actual_intent != expected_final_intent.lower():
            errors.append(
                f"[{name}] expected_final_intent: expected {expected_final_intent!r}, "
                f"got {actual_intent!r}"
            )

    obtained_terminal = "INCOMPLETE"
    if transcript:
        last_action = (transcript[-1].get("action") or "").upper()
        if last_action == "HANDOFF_VENDOR":
            obtained_terminal = "HANDOFF_VENDOR"
        elif last_action == "NO_REPLY":
            obtained_terminal = "SILENCE"
        else:
            obtained_terminal = last_action

    run = ScenarioRunResult(
        ok=False,
        errors=errors,
        name=name,
        turns=transcript,
        vendor_summary=vendor_summary,
        llm_real=llm_real,
        final_state=state,
        obtained_terminal=obtained_terminal,
        crm_report=crm_report,
        fallback_count=fallback_count,
        retry_count=0,
        traces=traces,
        clock_iso=clock_iso,
        seed_version=SEED_VERSION,
        understanding_model=understanding_model,
        composer_model=composer_model,
        summary_validation=summary_validation,
        summary_llm_rejected=summary_llm_rejected,
        summary_used_fallback=summary_used_fallback,
        invariants_executed=list(INVARIANT_CATALOG),
    )
    for v in check_scenario(scenario=scenario, result=run, llm_real=llm_real):
        errors.append(str(v))
    run.errors = errors
    run.ok = len(errors) == 0
    run.technical_status = "TECHNICAL_PASS" if run.ok else "TECHNICAL_FAIL"
    return run


def format_conversation(result: ScenarioRunResult) -> str:
    """WhatsApp-style raw transcript for human review."""
    lines: list[str] = []
    lines.append(f"## {result.name}")
    if result.llm_real:
        lines.append("_modo: LLM real · contexto limpo no início (equivalente a `/deletar`)_")
    else:
        lines.append("_modo: determinístico (understand stubado)_")
    lines.append("")
    for turn in result.turns:
        lines.append(f"**Cliente:** {turn['inbound']}")
        for bubble in turn.get("outbound") or []:
            lines.append(f"**Júlia:** {bubble}")
        for card in turn.get("vehicle_cards") or []:
            title = card.get("title") or " ".join(
                str(card.get(k) or "") for k in ("brand", "model", "version")
            ).strip()
            lines.append(
                f"**Card:** {title} · id={card.get('inventory_id')} · "
                f"{card.get('year')} · {card.get('price')} · {card.get('mileage')} km · "
                f"{card.get('color')} · {card.get('transmission')} · fotos={card.get('media_count')}"
            )
            for url in card.get("media_urls") or []:
                lines.append(f"**Mídia:** image {url}")
        for media in turn.get("outbound_media") or []:
            cap = (media.get("caption") or "").strip()
            url = media.get("url") or ""
            if url and url not in " ".join(lines[-8:]):
                lines.append(f"**Mídia:** {media.get('mediatype') or 'image'} {url}")
            if cap:
                lines.append(f"**Caption:** {cap}")
        if not turn.get("outbound") and not turn.get("vehicle_cards"):
            lines.append("**Júlia:** _(sem resposta)_")
        meta = []
        if turn.get("action"):
            meta.append(turn["action"])
        if turn.get("ask_field"):
            meta.append(f"ask={turn['ask_field']}")
        if turn.get("intent"):
            meta.append(f"intent={turn['intent']}")
        if meta:
            lines.append(f"_{' · '.join(meta)}_")
        lines.append("")
    if result.vendor_summary:
        lines.append("**Resumo CRM (juliaSummary):**")
        lines.append(result.vendor_summary)
        lines.append("")
    lines.append("`/deletar`")
    lines.append("")
    return "\n".join(lines)


def _print_report(results: dict[str, ScenarioRunResult]) -> None:
    passed = [n for n, r in results.items() if r.ok]
    failed = [n for n, r in results.items() if not r.ok]
    print(f"\n{'='*60}")
    print(f"Golden Scenario Results: {len(passed)} passed, {len(failed)} failed")
    print(f"{'='*60}")
    for name in passed:
        print(f"  ✅  {name}")
    for name in failed:
        r = results[name]
        print(f"  ❌  {name}")
        for e in r.errors:
            print(f"       {e}")


def write_transcripts(results: list[ScenarioRunResult]) -> Path:
    _TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _TRANSCRIPTS_DIR / "latest.md"
    chunks = ["# Golden scenarios — histórico bruto\n"]
    for r in results:
        chunks.append(format_conversation(r))
        chunks.append("---\n")
    path.write_text("\n".join(chunks), encoding="utf-8")
    traces_dir = _TRANSCRIPTS_DIR / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    crm_rows = []
    for r in results:
        (traces_dir / f"{r.name}.jsonl").write_text(
            "\n".join(json.dumps(row, default=str, ensure_ascii=False) for row in r.traces),
            encoding="utf-8",
        )
        crm_rows.append({
            "scenario": r.name,
            "summary_generated": bool(r.vendor_summary),
            "persist": r.crm_report,
            "technical_status": r.technical_status,
            "obtained_terminal": r.obtained_terminal,
        })
    (_TRANSCRIPTS_DIR / "crm_persist.json").write_text(
        json.dumps(crm_rows, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    report = {
        "technical_status_by_scenario": {r.name: r.technical_status for r in results},
        "terminals": {r.name: r.obtained_terminal for r in results},
        "failures": {r.name: r.errors for r in results if not r.ok},
        "invariants_executed_by_scenario": {
            r.name: list(r.invariants_executed)
            for r in results
        },
        "fallbacks": sum(r.fallback_count for r in results),
        "retries": sum(r.retry_count for r in results),
        "summaries_rejected": sum(1 for r in results if r.summary_llm_rejected),
        "summaries_deterministic_fallback": sum(1 for r in results if r.summary_used_fallback),
        "persist_verified": sum(
            1 for r in results if (r.crm_report or {}).get("matches_payload")
        ),
        "clock": results[0].clock_iso if results else None,
        "seed_version": results[0].seed_version if results else None,
        "understanding_model": results[0].understanding_model if results else None,
        "composer_model": results[0].composer_model if results else None,
        "human_review": {r.name: "PENDING_HUMAN_REVIEW" for r in results},
    }
    (_TRANSCRIPTS_DIR / "round_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


async def _maybe_live_pool() -> Any:
    try:
        from sdr.db import init_pool

        pool = await init_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return pool
    except Exception as exc:
        logging.getLogger(__name__).warning("live inventory pool unavailable: %s", exc)
        return None


async def _main(argv: list[str]) -> int:
    run_all = "--all" in argv
    show_trace = "--show-trace" in argv
    llm_real = "--llm-real" in argv
    names = [a for a in argv if not a.startswith("-")]

    if not run_all and not names:
        print("Usage: python -m sdr.replay <scenario_name|path> [--show-trace] [--llm-real]")
        print("       python -m sdr.replay --all [--show-trace] [--llm-real]")
        return 1

    if llm_real:
        from sdr.config import get_settings

        get_settings.cache_clear()
        key = (get_settings().openai_api_key or "").strip()
        if not key:
            print("ERROR: --llm-real requires OPENAI_API_KEY in apps/sdr/.env", file=sys.stderr)
            return 1

    scenarios_to_run: list[dict[str, Any]] = []
    if run_all:
        for p in list_scenarios():
            scenarios_to_run.append(json.loads(p.read_text()))
    else:
        for n in names:
            try:
                scenarios_to_run.append(load_scenario(n))
            except FileNotFoundError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1

    # Golden scenarios always use the seed inventory adapter so that results are
    # deterministic and independent of the live DB state.  A future flag like
    # ``--live-inventory`` can opt back into real DB inventory when needed.
    use_live_inventory = False
    live_pool = await _maybe_live_pool() if llm_real else None

    results: dict[str, ScenarioRunResult] = {}
    ordered: list[ScenarioRunResult] = []
    for scenario in scenarios_to_run:
        # Fresh canonical state per scenario == /deletar between conversations.
        run = await run_scenario_detailed(
            scenario,
            show_trace=show_trace or llm_real,
            pool=live_pool,
            llm_real=llm_real,
            use_live_inventory=use_live_inventory,
        )
        results[run.name] = run
        ordered.append(run)
        if llm_real:
            print("\n" + format_conversation(run))

    _print_report(results)
    if llm_real:
        path = write_transcripts(ordered)
        print(f"\nTranscripts written to {path}")
    failed_count = sum(1 for r in results.values() if not r.ok)
    return 0 if failed_count == 0 else 1


def main() -> None:
    """Entry point for `python -m sdr.replay`."""
    logging.basicConfig(level=logging.WARNING)
    argv = sys.argv[1:]
    sys.exit(asyncio.run(_main(argv)))


if __name__ == "__main__":
    main()
