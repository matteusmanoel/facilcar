"""Conversation replay harness.

Usage
-----
    # Deterministic mode (fixture-defined TurnFacts — validates full pipeline):
    python -m sdr.replay smoke_replay

    # Heuristic mode (no structured understanding — validates greeting policy only):
    python -m sdr.replay --mode heuristic smoke_replay

    # Live LLM (validates real semantic understanding):
    python -m sdr.replay --mode live smoke_replay
    LIVE_LLM=1 python -m sdr.replay smoke_replay

    # With real Postgres inventory (requires DATABASE_URL):
    python -m sdr.replay --with-db --mode live unseen_scooter_scenario

    # With turn trace:
    SDR_TRACE=true python -m sdr.replay smoke_replay

Fixture format
--------------
    name: "Scenario name"
    turns:
      - role: customer
        text: "Olá"
      - role: customer
        text: "Vocês têm algum scooter elétrico?"
        understanding:          # Optional: defines TurnFacts for deterministic mode.
          intent: purchase
          language: pt-BR
          facts_entries:
            - key: category
              value: scooter
          signals:
            explicit_handoff: null
            explicit_offer: null
            visit_intent: null
            high_purchase_intent: null
            sensitive_data_refusal: null
          confidence_entries:
            - key: intent
              value: 0.92

    assertions:
      no_reintro_after_first_turn: true
      commercial_intent_recognized: true
      state_persists_across_turns: true

    turn_assertions:
      - turn: 2
        intent: purchase
        action_not: smalltalk
        reason_not: greeting_or_chitchat
        facts_include:
          category: scooter
        no_greeting_in_response: true
        no_generic_restart: true

Mode behavior
-------------
- deterministic: turns with 'understanding:' use fixture-defined TurnFacts via the
  same UnderstandingFn interface. Turns without 'understanding:' use heuristic.
  Labeled in output as "DETERMINISTIC (fixture-injected TurnFacts)".
  Use this to prove the full pipeline — merge, decide, tool execute, compose —
  without live API calls.

- heuristic: all turns use heuristic extractor. Cannot validate open-ended
  commercial language. Labeled as "HEURISTIC (cannot prove semantic understanding)".

- live: uses the configured OpenAI provider for all turns. Requires OPENAI_API_KEY.
  Labeled as "LIVE (OPENAI_API_KEY)".

NOTE: heuristic mode CANNOT prove structured semantic fallback. Do not use it
as evidence that open-ended commercial language is understood.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"

# Phrases indicating a generic conversation restart. Used for no_generic_restart assertion.
_RESTART_PHRASES = [
    "como posso te ajudar hoje",
    "como posso ajudar você hoje",
    "como posso ajudar",
    "me conta, como posso ajudar",
    "em que posso te ajudar",
    "sou a júlia da facilcar",
    "soy júlia de facilcar",
    "¿en qué te puedo ayudar",
    "como puedo ayudarte",
]


def _find_fixture(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.exists():
        return p
    candidates = [
        FIXTURES_DIR / f"{name_or_path}.yaml",
        FIXTURES_DIR / f"{name_or_path}.yml",
        Path(name_or_path + ".yaml"),
        Path(name_or_path + ".yml"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"Fixture not found: {name_or_path!r}\nSearched: {[str(c) for c in candidates]}"
    )


def _parse_turn_facts_from_fixture(understanding: dict[str, Any], *, source_text: str = ""):
    """Parse TurnFacts from a fixture 'understanding:' block.

    Uses the same schema as the real LLM provider (json_schema strict).
    Injected through the UnderstandingFn interface — not a bypass.
    """
    from sdr.understanding.extractor import _parse_llm_payload

    return _parse_llm_payload(understanding, source_text=source_text)


def _make_deterministic_understand(turns_data: list[dict[str, Any]]):
    """Build an understanding function that injects fixture TurnFacts where defined,
    falling back to heuristic for turns without an 'understanding:' block.

    Both paths return TurnFacts through the same interface the real LLM uses.
    """
    turn_understanding: dict[str, Any] = {}
    for turn in turns_data:
        if turn.get("role") != "customer":
            continue
        if "understanding" not in turn:
            continue
        coalesce = turn.get("coalesce")
        if isinstance(coalesce, list) and coalesce:
            parts = [str(p.get("text") or "") for p in coalesce if isinstance(p, dict)]
            text = "\n".join(p for p in parts if p)
        else:
            text = str(turn.get("text") or "")
        turn_understanding[text] = _parse_turn_facts_from_fixture(
            turn["understanding"], source_text=text
        )

    async def understand(text: str, state: Any) -> Any:
        if text in turn_understanding:
            from sdr.understanding.extractor import _set_meta

            facts = turn_understanding[text]
            _set_meta(
                path="deterministic_fixture",
                provider="fixture_injected",
                canonical_fact_keys=list(facts.facts.keys()),
                signals_gated=facts.signals.as_dict(),
            )
            return facts
        from sdr.understanding.extractor import _heuristic_extract, _set_meta

        _set_meta(path="heuristic", provider="fixture_fallback")
        return _heuristic_extract(text)

    return understand, bool(turn_understanding)


def _facts_equal(actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    if str(actual) == str(expected):
        return True
    try:
        return float(actual) == float(expected)
    except (TypeError, ValueError):
        return False


def _print_boundary(
    *,
    turn_num: int,
    mode: str,
    state_before: Any,
    result: Any,
) -> None:
    """Print sanitized understanding boundary when SDR_TRACE is enabled."""
    if os.environ.get("SDR_TRACE", "").strip().lower() not in ("1", "true", "yes"):
        return

    from sdr.understanding.extractor import get_last_understanding_meta

    meta = get_last_understanding_meta()
    tf = result.turn_facts
    print(f"\n  --- TRACE BOUNDARY (turn {turn_num}) ---")
    print(f"  provider/path : {meta.get('provider')}/{meta.get('path')}")
    if meta.get("model"):
        print(f"  model         : {meta.get('model')}")
    if meta.get("raw_payload") is not None:
        raw = meta["raw_payload"]
        # Sanitize: only keys/intent/signals, not long blobs.
        safe_raw = {
            "intent": raw.get("intent") if isinstance(raw, dict) else None,
            "facts_entries": raw.get("facts_entries") if isinstance(raw, dict) else None,
            "signals": raw.get("signals") if isinstance(raw, dict) else None,
            "language": raw.get("language") if isinstance(raw, dict) else None,
            "confidence_entries": raw.get("confidence_entries") if isinstance(raw, dict) else None,
        }
        print(f"  raw LLM payload: {json.dumps(safe_raw, ensure_ascii=False)}")
    if meta.get("rejected_fact_keys"):
        print(f"  rejected keys : {meta.get('rejected_fact_keys')}")
    if meta.get("raw_fact_keys") is not None:
        print(f"  raw fact keys : {meta.get('raw_fact_keys')} → {meta.get('canonical_fact_keys')}")
    print(
        f"  TurnFacts     : intent={tf.intent.value} facts={tf.facts} "
        f"signals={tf.signals.as_dict()} confidence={tf.confidence} "
        f"budget_status={getattr(tf.budget_status, 'value', tf.budget_status)} "
        f"pending_resolution={getattr(tf.pending_resolution, 'value', tf.pending_resolution)} "
        f"alternative_scope={getattr(tf.alternative_scope, 'value', tf.alternative_scope)}"
    )
    if meta.get("llm_high_purchase_raw") is not None:
        print(
            f"  high_purchase : llm_raw={meta.get('llm_high_purchase_raw')} "
            f"gated={tf.signals.high_purchase_intent}"
        )
    before_facts = {k: v for k, v in state_before.facts.items() if not str(k).startswith("_")}
    after_facts = {k: v for k, v in result.state.facts.items() if not str(k).startswith("_")}
    print(
        f"  state before  : intent={state_before.intent.value} "
        f"facts={before_facts} "
        f"lifecycle={state_before.lifecycle.status.value} "
        f"pending={state_before.pending_interaction.value} "
        f"scope={state_before.alternative_scope.value} "
        f"budget_status={state_before.budget_status.value}"
    )
    print(
        f"  state after   : intent={result.state.intent.value} "
        f"facts={after_facts} "
        f"lifecycle={result.state.lifecycle.status.value} "
        f"pending={result.state.pending_interaction.value} "
        f"scope={result.state.alternative_scope.value} "
        f"budget_status={result.state.budget_status.value} "
        f"inv_key={result.state.last_inventory_search_key} "
        f"inv_outcome={result.state.last_inventory_outcome}"
    )
    print(
        f"  ActionPlan    : action={result.action_plan.action.value} "
        f"reason={result.action_plan.reason_code} "
        f"tools={[t.get('tool') for t in result.action_plan.tool_calls]}"
    )
    print(f"  ToolResults   : {result.tool_results}")
    if result.response_directive is not None:
        d = result.response_directive
        print(
            f"  Directive     : inventory_outcome={d.inventory_outcome.value} "
            f"allowed={d.claims_allowed} forbidden_stock={[c for c in d.claims_forbidden if 'stock' in c or 'absence' in c or 'no_' in c]}"
        )
    if result.validator_result is not None:
        print(f"  Validator     : {result.validator_result}")
    print(f"  --- end TRACE ---")



def _print_turn_summary(
    turn_num: int,
    text: str,
    *,
    result: Any,
    state_before: Any,
    mode: str,
) -> None:
    print(f"\n{'='*60}")
    print(f"TURN {turn_num}  [{mode}]")
    print(f"  inbound   : {text[:100]!r}")
    print(f"  intent    : {state_before.intent.value!r} → {result.state.intent.value!r}")
    print(f"  lifecycle : {state_before.lifecycle.status.value!r} → {result.state.lifecycle.status.value!r}")
    print(f"  action    : {result.action_plan.action.value!r}  reason={result.action_plan.reason_code!r}")
    if result.state.facts:
        safe_facts = {k: v for k, v in result.state.facts.items() if not k.startswith("_")}
        print(f"  facts     : {safe_facts}")
    else:
        print(f"  facts     : (empty)")
    if result.action_plan.tool_calls:
        print(f"  planned tools  : {[t['tool'] for t in result.action_plan.tool_calls]}")
        print(f"  executed tools : {[r.get('tool') for r in result.tool_results]}")
        for tr in result.tool_results:
            if tr.get("tool") == "inventory_search":
                if tr.get("error"):
                    print(f"  inventory  : ERROR {tr['error']}")
                elif tr.get("found"):
                    print(f"  inventory  : {tr['count']} vehicle(s) found")
                else:
                    print(f"  inventory  : 0 found (params={tr.get('search_params')})")
            elif tr.get("error"):
                print(f"  tool error : {tr['tool']} → {tr['error']}")
    if result.outbound_texts:
        print(f"  response ({len(result.outbound_texts)} bubble(s)):")
        for b in result.outbound_texts:
            print(f"    > {b}")
    else:
        print("  response  : [no reply]")


def _check_turn_assertions(
    turn_num: int,
    turn_assertion: dict[str, Any],
    result: Any,
    state_before: Any,
) -> list[str]:
    """Check per-turn semantic assertions. Returns list of failure messages."""
    failures: list[str] = []
    prefix = f"turn {turn_num}"
    state_after = result.state
    action = result.action_plan.action.value
    reason = result.action_plan.reason_code or ""
    bubbles_lower = " ".join(result.outbound_texts).lower()

    # intent assertion
    expected_intent = turn_assertion.get("intent")
    if expected_intent and state_after.intent.value != expected_intent:
        failures.append(
            f"{prefix}: expected intent={expected_intent!r}, got {state_after.intent.value!r}"
        )

    # action_not assertion
    action_not = turn_assertion.get("action_not")
    if action_not and action == action_not:
        failures.append(
            f"{prefix}: action must not be {action_not!r}, but got {action!r}"
        )

    # reason_not assertion
    reason_not = turn_assertion.get("reason_not")
    if reason_not and reason == reason_not:
        failures.append(
            f"{prefix}: reason must not be {reason_not!r}, but got {reason!r}"
        )

    # facts_include assertion
    facts_include = turn_assertion.get("facts_include") or {}
    for k, v in facts_include.items():
        actual = state_after.facts.get(k)
        if not _facts_equal(actual, v):
            failures.append(
                f"{prefix}: expected facts[{k!r}]={v!r}, got {actual!r}"
            )

    # prior_facts_preserved assertion (facts from state_before must still be present)
    prior_facts = turn_assertion.get("prior_facts_preserved") or {}
    for k, v in prior_facts.items():
        actual = state_after.facts.get(k)
        if not _facts_equal(actual, v):
            failures.append(
                f"{prefix}: prior fact {k!r}={v!r} was lost; got {actual!r}"
            )

    expected_budget_status = turn_assertion.get("budget_status")
    if expected_budget_status:
        actual_bs = state_after.budget_status.value
        if actual_bs != expected_budget_status:
            failures.append(
                f"{prefix}: expected budget_status={expected_budget_status!r}, got {actual_bs!r}"
            )

    expected_scope = turn_assertion.get("alternative_scope")
    if expected_scope:
        actual_scope = state_after.alternative_scope.value
        if actual_scope != expected_scope:
            failures.append(
                f"{prefix}: expected alternative_scope={expected_scope!r}, got {actual_scope!r}"
            )

    expected_pending = turn_assertion.get("pending_interaction")
    if expected_pending is not None:
        actual_pending = state_after.pending_interaction.value
        if actual_pending != expected_pending:
            failures.append(
                f"{prefix}: expected pending_interaction={expected_pending!r}, got {actual_pending!r}"
            )

    if turn_assertion.get("inventory_outcome"):
        expected_out = turn_assertion["inventory_outcome"]
        actual_out = None
        for tr in result.tool_results:
            if tr.get("tool") == "inventory_search":
                actual_out = tr.get("outcome")
                break
        if actual_out != expected_out:
            failures.append(
                f"{prefix}: expected inventory_outcome={expected_out!r}, got {actual_out!r}"
            )

    if turn_assertion.get("search_key_changed"):
        if state_after.last_inventory_search_key == state_before.last_inventory_search_key:
            failures.append(
                f"{prefix}: expected inventory search key to change; "
                f"got {state_after.last_inventory_search_key!r}"
            )

    if turn_assertion.get("action"):
        if action != turn_assertion["action"]:
            failures.append(
                f"{prefix}: expected action={turn_assertion['action']!r}, got {action!r}"
            )

    if turn_assertion.get("no_budget_question"):
        budget_q = ("orçamento", "orcamento", "valor máximo", "investir")
        if any(q in bubbles_lower for q in budget_q):
            failures.append(
                f"{prefix}: must not ask budget again; got {result.outbound_texts!r}"
            )

    if turn_assertion.get("no_rigid_corolla_requirement"):
        rigid = (
            "que legal que você quer um corolla",
            "orçamento que você está pensando para o corolla",
            "pensando para o corolla",
        )
        if any(p in bubbles_lower for p in rigid):
            failures.append(
                f"{prefix}: must not treat Corolla as rigid requirement after ANY_VEHICLE; "
                f"got {result.outbound_texts!r}"
            )

    # no_greeting_in_response assertion
    if turn_assertion.get("no_greeting_in_response"):
        greeting_phrases = ["sou a júlia da facilcar", "soy júlia de facilcar", "sou a júlia"]
        for phrase in greeting_phrases:
            if phrase in bubbles_lower:
                failures.append(
                    f"{prefix}: response must not introduce Júlia; found {phrase!r} in {result.outbound_texts!r}"
                )
                break

    # no_generic_restart assertion
    if turn_assertion.get("no_generic_restart"):
        for phrase in _RESTART_PHRASES:
            if phrase in bubbles_lower:
                failures.append(
                    f"{prefix}: response must not produce a generic restart; found {phrase!r} in {result.outbound_texts!r}"
                )
                break

    return failures


def _check_global_assertions(
    assertions: dict[str, Any],
    history: list[dict[str, Any]],
) -> list[str]:
    """Check global (all-turn) assertions. Returns list of failure messages."""
    failures: list[str] = []
    if not history:
        return failures

    if assertions.get("no_reintro_after_first_turn"):
        for i, h in enumerate(history[1:], start=2):
            bl = " ".join(h["outbound"]).lower()
            if "sou a júlia" in bl or "soy júlia" in bl:
                failures.append(
                    f"no_reintro_after_first_turn: turn {i} contained introduction"
                )

    if assertions.get("commercial_intent_recognized"):
        commercial = {"purchase", "purchase_financing", "trade", "sale", "consignment", "refinancing"}
        if not any(h["intent_after"] in commercial for h in history):
            failures.append(
                "commercial_intent_recognized: no commercial intent in any turn"
            )

    if assertions.get("tool_executed_inventory"):
        if not any(
            any(t.get("tool") == "inventory_search" for t in h["tool_results"])
            for h in history
        ):
            failures.append(
                "tool_executed_inventory: inventory_search was not executed in any turn"
            )

    if assertions.get("state_persists_across_turns"):
        if len(history) > 1 and history[-1]["assistant_turn_count"] <= 0:
            failures.append(
                "state_persists_across_turns: assistant_turn_count did not increment"
            )

    return failures


async def run_replay(
    fixture_path: str,
    mode: str = "deterministic",
    *,
    with_db: bool = False,
) -> bool:
    """Run the replay. Returns True on success, False on assertion failure.

    mode:
      deterministic - fixture-injected TurnFacts for turns with 'understanding:' block
      heuristic     - all turns use heuristic extractor (CANNOT prove semantic understanding)
      live          - uses OpenAI provider for all turns
    """
    path = _find_fixture(fixture_path)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    name = data.get("name", path.stem)
    turns_data = data.get("turns") or []
    assertions = data.get("assertions") or {}
    turn_assertions_raw: list[dict[str, Any]] = data.get("turn_assertions") or []
    # Index by turn number for fast lookup.
    turn_assertions: dict[int, dict[str, Any]] = {
        int(ta["turn"]): ta for ta in turn_assertions_raw if "turn" in ta
    }

    # Override mode from env.
    if os.environ.get("LIVE_LLM", "").strip().lower() in ("1", "true", "yes"):
        mode = "live"

    print(f"\n🔁 REPLAY: {name}")
    print(f"   fixture : {path}")
    print(f"   turns   : {len(turns_data)}")

    if mode == "live":
        from sdr.orchestrator import default_understand
        understand = default_understand
        mode_label = "LIVE (OPENAI_API_KEY)"
        has_deterministic = False
    elif mode == "heuristic":
        from sdr.understanding.extractor import _heuristic_extract

        async def understand(text: str, state: Any) -> Any:
            return _heuristic_extract(text)

        mode_label = "HEURISTIC (cannot prove semantic understanding)"
        has_deterministic = False
    else:
        understand, has_deterministic = _make_deterministic_understand(turns_data)
        mode_label = "DETERMINISTIC (fixture-injected TurnFacts)" if has_deterministic else "HEURISTIC (no fixture understanding defined)"

    print(f"   mode    : {mode_label}")
    if os.environ.get("SDR_TRACE", "").strip().lower() in ("1", "true", "yes"):
        from sdr.trace import configure_trace_logging

        configure_trace_logging()
        print("   trace   : ENABLED (boundary dump per turn)")
    if mode not in ("live",) and not has_deterministic and turn_assertions:
        print(
            "\n⚠️  WARNING: turn_assertions require deterministic or live mode.\n"
            "    Heuristic mode cannot validate open-ended commercial language.\n"
            "    Per-turn semantic assertions will likely fail.\n"
        )

    from sdr.domain.types import ConversationCanonicalState, CustomerState

    state = ConversationCanonicalState(
        thread_id="replay-thread",
        customer=CustomerState(phone="replay-customer"),
    )

    pool = None
    if with_db:
        from sdr.config import get_settings
        from sdr.db import close_pool, init_pool

        cfg = get_settings()
        try:
            pool = await init_pool(cfg)
        except Exception as exc:  # noqa: BLE001 — surface as harness failure
            print(f"\n❌ --with-db failed to init pool: {type(exc).__name__}: {exc}")
            return False
        print("   db      : CONNECTED (inventory_search enabled)")
    else:
        print("   db      : off (pool=None → inventory_search=no_db_pool)")

    history: list[dict[str, Any]] = []
    print(f"\n{'='*60}")
    print(f"INITIAL STATE: intent=unknown  lifecycle=BOT_ACTIVE  assistant_turn_count=0")

    from sdr.application.process_turn import process_turn

    customer_turn_num = 0
    all_failures: list[str] = []

    try:
        for turn in turns_data:
            if turn.get("role") != "customer":
                continue
            customer_turn_num += 1
            coalesce = turn.get("coalesce")
            if isinstance(coalesce, list) and coalesce:
                parts = [str(p.get("text") or "") for p in coalesce if isinstance(p, dict)]
                text = "\n".join(p for p in parts if p)
                print(
                    f"\n  [coalesce] {len(parts)} bubbles → 1 InboundTurn "
                    f"({len(text)} chars)"
                )
            else:
                text = str(turn.get("text") or "")

            state_before = state

            result = await process_turn(
                state=state,
                inbound_text=text,
                understand=understand,
                pool=pool,
            )
            if result.outbound_texts:
                result.state.assistant_turn_count = state.assistant_turn_count + 1
            state = result.state

            _print_turn_summary(
                customer_turn_num, text, result=result, state_before=state_before, mode=mode_label
            )
            _print_boundary(
                turn_num=customer_turn_num,
                mode=mode_label,
                state_before=state_before,
                result=result,
            )

            # Check per-turn assertions.
            ta = turn_assertions.get(customer_turn_num)
            if ta:
                turn_failures = _check_turn_assertions(customer_turn_num, ta, result, state_before)
                if turn_failures:
                    print(f"\n  ❌ TURN {customer_turn_num} ASSERTIONS FAILED:")
                    for f in turn_failures:
                        print(f"    - {f}")
                else:
                    print(f"\n  ✅ turn {customer_turn_num} assertions passed")
                all_failures.extend(turn_failures)

            history.append(
                {
                    "turn": customer_turn_num,
                    "inbound": text,
                    "intent_before": state_before.intent.value,
                    "intent_after": result.state.intent.value,
                    "lifecycle_after": result.state.lifecycle.status.value,
                    "action": result.action_plan.action.value,
                    "outbound": result.outbound_texts,
                    "tool_results": result.tool_results,
                    "assistant_turn_count": result.state.assistant_turn_count,
                }
            )
    finally:
        if with_db:
            from sdr.db import close_pool

            await close_pool()

    # Global assertions.
    global_failures = _check_global_assertions(assertions, history)
    all_failures.extend(global_failures)

    print(f"\n{'='*60}")
    if all_failures:
        print("❌ ASSERTIONS FAILED:")
        for f in all_failures:
            print(f"  - {f}")
        return False

    total = len(turn_assertions) + len(assertions)
    print(f"✅ ALL ASSERTIONS PASSED ({total} checks)")
    return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="SDR conversation replay harness")
    parser.add_argument("fixture", help="Fixture name or path")
    parser.add_argument(
        "--mode",
        choices=["deterministic", "heuristic", "live"],
        default="deterministic",
        help="Understanding mode (default: deterministic)",
    )
    parser.add_argument(
        "--with-db",
        action="store_true",
        help="Init asyncpg pool from DATABASE_URL so inventory_search queries real stock",
    )
    args = parser.parse_args()
    env_with_db = os.environ.get("SDR_REPLAY_WITH_DB", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    ok = asyncio.run(run_replay(args.fixture, mode=args.mode, with_db=args.with_db or env_with_db))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
