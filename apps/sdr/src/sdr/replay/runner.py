"""Golden scenario runner used by the replay CLI and by pytest.

Usage (from repo root via uv):
    uv run -m sdr.replay fox_peugeot_troca
    uv run -m sdr.replay --all
    uv run -m sdr.replay --show-trace civic_vendido_foto
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCENARIOS_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "golden" / "scenarios"


def list_scenarios() -> list[Path]:
    return sorted(_SCENARIOS_DIR.glob("*.json"))


def load_scenario(name_or_path: str) -> dict[str, Any]:
    p = Path(name_or_path)
    if not p.exists():
        # Try by name (without .json)
        candidate = _SCENARIOS_DIR / f"{name_or_path}.json"
        if candidate.exists():
            p = candidate
        else:
            raise FileNotFoundError(f"Scenario not found: {name_or_path!r}")
    return json.loads(p.read_text())


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_scenario(
    scenario: dict[str, Any],
    *,
    show_trace: bool = False,
    pool: Any = None,
) -> tuple[bool, list[str]]:
    """Run a golden scenario. Returns (ok, errors)."""
    import unittest.mock as mock

    from sdr.application.process_turn import process_turn
    from sdr.domain.types import (
        BusinessIntent,
        ConversationCanonicalState,
        CustomerState,
        TurnFacts,
    )
    from tests.golden.invariants import InvariantViolation, check_turn

    name = scenario.get("name", "unknown")
    turns = scenario.get("turns", [])

    # Build initial state
    init = scenario.get("initial_state") or {}
    state = ConversationCanonicalState(
        thread_id=f"replay_{name}",
        customer=CustomerState(phone="5541999999999"),
    )
    for k, v in init.items():
        if not hasattr(state, k):
            continue
        # Convert intent strings to BusinessIntent enum
        if k == "intent" and isinstance(v, str):
            try:
                v = BusinessIntent(v.lower())
            except ValueError:
                pass
        setattr(state, k, v)

    errors: list[str] = []

    # Patch inventory search to return SUCCESS_EMPTY so the Decision Engine
    # can track last_inventory_search_key and progress past SHOW_OFFERS.
    # Scenarios that want to assert specific inventory outcomes should use
    # per-turn `inventory_outcome_stub` (not yet implemented) or YAML fixtures.
    async def _fake_inventory_search(fake_pool: Any, req: Any) -> list:
        return []

    # Build per-turn understand stubs.
    # Each turn may define `understand_return` with intent + facts to inject.
    understand_stubs: list[dict[str, Any]] = [
        t.get("understand_return") or {} for t in turns
    ]

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
        # Handle signals
        from sdr.domain.types import HandoffSignals
        signals_raw = stub.get("signals") or {}
        if signals_raw:
            valid_fields = {f.name for f in HandoffSignals.__dataclass_fields__.values()}
            signals = HandoffSignals(**{k: v for k, v in signals_raw.items() if k in valid_fields})
        else:
            signals = HandoffSignals()
        return TurnFacts(intent=intent, facts=facts, signals=signals)

    for idx, turn_def in enumerate(turns):
        turn_idx_ref[0] = idx
        inbound_text = turn_def.get("inbound", "")
        vehicle_hint = turn_def.get("inbound_vehicle_hint")

        if vehicle_hint:
            state.facts["vehicle_hint_model"] = vehicle_hint

        if show_trace:
            print(f"\n{'='*60}")
            print(f"  Turn {idx}: {inbound_text!r}")
            print(f"  State facts before: {dict(state.facts)}")

        try:
            with mock.patch("sdr.tools.inventory.search_with_request", side_effect=_fake_inventory_search):
                result = await process_turn(
                    state=state,
                    inbound_text=inbound_text,
                    understand=_understand,
                    pool=object(),  # non-None so tool_executor doesn't short-circuit
                )
        except Exception as exc:
            errors.append(f"[{name}] turn {idx}: process_turn raised {type(exc).__name__}: {exc}")
            break

        if show_trace:
            plan = result.action_plan
            print(f"  Stub understand: intent={understand_stubs[idx].get('intent', 'UNKNOWN')}")
            print(f"  Action: {plan.action.value if hasattr(plan.action, 'value') else plan.action}")
            print(f"  ask_field: {plan.ask_field}")
            print(f"  Outbound: {result.outbound_texts}")
            if result.tool_results:
                for tr in result.tool_results:
                    print(f"  ToolResult: {tr.get('tool')} outcome={tr.get('outcome')}")

        violations = check_turn(
            scenario_name=name,
            turn_idx=idx,
            turn_def=turn_def,
            result=result,
        )
        for v in violations:
            errors.append(str(v))

        state = result.state

    return (len(errors) == 0), errors


def _print_report(results: dict[str, tuple[bool, list[str]]]) -> None:
    passed = [n for n, (ok, _) in results.items() if ok]
    failed = [n for n, (ok, _) in results.items() if not ok]
    print(f"\n{'='*60}")
    print(f"Golden Scenario Results: {len(passed)} passed, {len(failed)} failed")
    print(f"{'='*60}")
    for name in passed:
        print(f"  ✅  {name}")
    for name in failed:
        _, errs = results[name]
        print(f"  ❌  {name}")
        for e in errs:
            print(f"       {e}")


async def _main(argv: list[str]) -> int:
    run_all = "--all" in argv
    show_trace = "--show-trace" in argv

    # Filter flags
    names = [a for a in argv if not a.startswith("-")]

    if not run_all and not names:
        print("Usage: python -m sdr.replay <scenario_name|path> [--show-trace]")
        print("       python -m sdr.replay --all [--show-trace]")
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

    results: dict[str, tuple[bool, list[str]]] = {}
    for scenario in scenarios_to_run:
        ok, errors = await run_scenario(scenario, show_trace=show_trace)
        results[scenario.get("name", "unknown")] = (ok, errors)

    _print_report(results)
    failed_count = sum(1 for ok, _ in results.values() if not ok)
    return 0 if failed_count == 0 else 1


def main() -> None:
    """Entry point for `python -m sdr.replay`."""
    logging.basicConfig(level=logging.WARNING)
    argv = sys.argv[1:]
    sys.exit(asyncio.run(_main(argv)))


if __name__ == "__main__":
    main()
