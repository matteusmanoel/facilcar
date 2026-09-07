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
    import unittest.mock as mock

    from sdr.application.process_turn import process_turn
    from sdr.domain.types import Action
    from tests.golden.invariants import check_turn

    name = scenario.get("name", "unknown")
    turns = scenario.get("turns", [])
    state = _initial_state(scenario)
    errors: list[str] = []
    transcript: list[dict[str, Any]] = []
    vendor_summary: str | None = None

    async def _seed_run_inventory_search(state: Any, _pool: Any) -> dict[str, Any]:
        """Seed-based _run_inventory_search for golden scenarios.

        Replaces the real DB call with seed_inventory.json data so that golden
        scenarios can assert on SUCCESS_FOUND / SUCCESS_SOLD / SUCCESS_EMPTY
        without touching a live database.
        """
        from sdr.domain.inventory_outcome import inventory_result
        from sdr.domain.inventory_search import build_inventory_search_request
        from sdr.domain.types import InventoryOutcome
        from tests.golden.fixtures.seed_inventory_adapter import search_seed

        req = build_inventory_search_request(
            state.facts,
            alternative_scope=state.alternative_scope,
            budget_status=state.budget_status,
            limit=3,
        )
        # InventorySearchRequest uses original_model / original_brand (not .model / .brand).
        model = (
            getattr(req, "original_model", None)
            or getattr(req, "model", None)
            or ""
        )
        brand = (
            getattr(req, "original_brand", None)
            or getattr(req, "brand", None)
            or ""
        )

        # Check for scenario-level vehicle hint (e.g. for civic_vendido_foto).
        vehicle_hint_id = state.facts.get("_seed_vehicle_hint") or None

        result = search_seed(model=model, brand=brand, vehicle_hint_id=vehicle_hint_id)
        outcome_str = result.get("outcome", "SUCCESS_EMPTY")
        search_params = req.as_trace_dict() if hasattr(req, "as_trace_dict") else {}

        if outcome_str == "SUCCESS_FOUND":
            vehicles = result.get("vehicles") or []
            return inventory_result(
                outcome=InventoryOutcome.SUCCESS_FOUND,
                count=len(vehicles),
                vehicles=vehicles,
                alternatives=vehicles[:3],
                search_params=search_params,
            )
        elif outcome_str == "SUCCESS_SOLD":
            vehicle = result.get("vehicle") or {}
            return inventory_result(
                outcome=InventoryOutcome.SUCCESS_SOLD,
                count=0,
                vehicles=[vehicle],
                alternatives=[],
                search_params=search_params,
            )
        else:
            return inventory_result(
                outcome=InventoryOutcome.SUCCESS_EMPTY,
                count=0,
                vehicles=[],
                alternatives=[],
                search_params=search_params,
            )

    if llm_real:
        from sdr.orchestrator import default_understand

        understand = default_understand
        turn_idx_ref = [0]
        understand_stubs: list[dict[str, Any]] = []
    else:
        understand, turn_idx_ref, understand_stubs = _stub_understand(turns)

    process_pool = pool if pool is not None else object()

    for idx, turn_def in enumerate(turns):
        turn_idx_ref[0] = idx
        inbound_text = turn_def.get("inbound", "")
        vehicle_hint = turn_def.get("inbound_vehicle_hint")

        if vehicle_hint:
            state.facts["vehicle_hint_model"] = vehicle_hint

        if show_trace:
            print(f"\n{'='*60}")
            print(f"  Turn {idx}: {inbound_text!r}")
            print(f"  assistant_turn_count: {state.assistant_turn_count}")
            print(f"  State facts before: {dict(state.facts)}")

        try:
            # Apply scenario-level vehicle hint to state if present.
            scenario_hint = scenario.get("seed_vehicle_hint")
            if scenario_hint and not state.facts.get("_seed_vehicle_hint"):
                state.facts["_seed_vehicle_hint"] = scenario_hint

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
                    inbound_text=inbound_text,
                    understand=understand,
                    pool=process_pool,
                )
        except Exception as exc:
            errors.append(f"[{name}] turn {idx}: process_turn raised {type(exc).__name__}: {exc}")
            break

        plan = result.action_plan
        action_val = plan.action.value if hasattr(plan.action, "value") else str(plan.action)
        facts_out = {
            k: v for k, v in result.turn_facts.facts.items() if v is not None
        } if result.turn_facts else {}
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
        })

        if show_trace:
            if not llm_real and idx < len(understand_stubs):
                print(f"  Stub understand: intent={understand_stubs[idx].get('intent', 'UNKNOWN')}")
            else:
                print(f"  Understand: intent={result.turn_facts.intent.value} facts={facts_out}")
            print(f"  Action: {action_val}")
            print(f"  ask_field: {plan.ask_field}")
            print(f"  should_introduce: {transcript[-1]['should_introduce']}")
            print(f"  Outbound: {result.outbound_texts}")
            if result.tool_results:
                for tr in result.tool_results:
                    print(f"  ToolResult: {tr.get('tool')} outcome={tr.get('outcome')}")

        skip_routing = llm_real
        turn_for_check = dict(turn_def)
        if skip_routing:
            # In LLM-real mode: strip only deterministic routing assertions.
            # Semantic/safety assertions (forbidden_in_outbound, required_in_outbound_any,
            # expected_in_outbound_one_of) are kept — they are the quality gate.
            turn_for_check.pop("expected_action", None)
            turn_for_check.pop("expected_ask_field_in", None)
            turn_for_check.pop("expected_facts_after", None)
            # Merge llm_real_only into the check dict when running LLM-real.
            llm_real_only = turn_def.get("llm_real_only") or {}
            turn_for_check.update(llm_real_only)
        else:
            # In stub mode: strip llm_real_only assertions entirely (Composer
            # fallback does not call suggest_visit_slots, etc.).
            turn_for_check.pop("llm_real_only", None)
            turn_for_check.pop("invariant_two_concrete_slots", None)
        violations = check_turn(
            scenario_name=name,
            turn_idx=idx,
            turn_def=turn_for_check,
            result=result,
        )
        for v in violations:
            errors.append(str(v))

        if plan.action == Action.HANDOFF_VENDOR or plan.handoff:
            from sdr.domain.vendor_summary import build_vendor_summary

            try:
                vendor_summary = build_vendor_summary(result.state)
            except Exception as exc:
                vendor_summary = f"(summary failed: {exc})"
            if show_trace:
                print(f"  CRM juliaSummary: {vendor_summary}")

        state = result.state

    # Post-scenario: validate expected_final_intent (LLM-real only — stub mode
    # uses understand_return which forces the intent, making this trivially true).
    expected_final_intent = scenario.get("expected_final_intent")
    if expected_final_intent and llm_real and turns:
        actual_intent = state.intent.value if hasattr(state.intent, "value") else str(state.intent)
        if actual_intent != expected_final_intent.lower():
            errors.append(
                f"[{name}] expected_final_intent: expected {expected_final_intent!r}, "
                f"got {actual_intent!r} — LLM misclassified the intent"
            )

    return ScenarioRunResult(
        ok=len(errors) == 0,
        errors=errors,
        name=name,
        turns=transcript,
        vendor_summary=vendor_summary,
        llm_real=llm_real,
    )


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
        if not turn.get("outbound"):
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
