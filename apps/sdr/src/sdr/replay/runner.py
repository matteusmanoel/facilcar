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
    composer_retries: int = 0
    questions_rejected: int = 0
    traces: list[dict[str, Any]] = field(default_factory=list)
    clock_iso: str | None = None
    seed_version: str | None = None
    understanding_model: str | None = None
    composer_model: str | None = None
    technical_status: str = "TECHNICAL_FAIL"
    summary_validation: dict[str, Any] | None = None
    summary_llm_rejected: bool = False
    summary_used_fallback: bool = False
    summary_llm_attempted: bool = False
    summary_empty_claims_rejected: bool = False
    summary_origin: str = ""
    summary_used_llm: bool = False
    dialogue_misaligned: int = 0
    invariants_executed: list[str] = field(default_factory=list)
    runtime_calls: int = 0
    location_sends: int = 0
    inbound_batches: list[dict[str, Any]] = field(default_factory=list)
    commercial_observations: list[dict[str, Any]] = field(default_factory=list)
    seed_sha256: str | None = None
    inventory_source: str = "seed_isolated"
    identification_source: str | None = None
    first_inbound: str | None = None
    visual_turns: int = 0
    llm_calls: int = 0
    suppressed_outbound_count: int = 0
    suppressed_outbound_reasons: list[str] = field(default_factory=list)
    inbound_persisted: list[dict[str, Any]] = field(default_factory=list)
    events_executed: list[dict[str, Any]] = field(default_factory=list)
    crm_handoff_count: int = 0
    crm_lead_id: str | None = None
    bot_status: str | None = None
    ownership_revision: int = 0
    followup_tasks: list[dict[str, Any]] = field(default_factory=list)
    followup_sends: int = 0
    followup_composer_calls: int = 0
    wait_state: str | None = None
    clock_jumps: list[dict[str, Any]] = field(default_factory=list)
    followup_cancels: list[dict[str, Any]] = field(default_factory=list)
    followup_claims: list[dict[str, Any]] = field(default_factory=list)
    followup_transitions: list[dict[str, Any]] = field(default_factory=list)
    inventory_overrides: list[dict[str, Any]] = field(default_factory=list)
    idempotency_keys: list[str] = field(default_factory=list)
    execution_mode: str = "production_policy"
    followup_evidence: dict[str, Any] = field(default_factory=dict)
    execution_meta: dict[str, Any] = field(default_factory=dict)



# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _initial_state(scenario: dict[str, Any]) -> Any:
    from sdr.domain.types import BusinessIntent, ConversationCanonicalState, CustomerState

    name = scenario.get("name", "unknown")
    init = scenario.get("initial_state") or {}
    customer = scenario.get("customer") or {}
    state = ConversationCanonicalState(
        thread_id=f"replay_{name}",
        customer=CustomerState(
            phone=str(customer.get("phone") or "5541999999999"),
            name=customer.get("name"),
        ),
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


def _stub_understand(turns: list[dict[str, Any]], *, copy_followup_hints: bool = False):
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
        facts = dict(stub.get("facts") or {})
        pause = facts.pop("pause_reason", None)
        consent = facts.pop("consent_level", None)
        temporal = facts.pop("temporal_text", None)
        signals_raw = stub.get("signals") or {}
        if signals_raw:
            valid_fields = {f.name for f in HandoffSignals.__dataclass_fields__.values()}
            signals = HandoffSignals(**{k: v for k, v in signals_raw.items() if k in valid_fields})
        else:
            signals = HandoffSignals()
        tf = TurnFacts(intent=intent, facts=facts, signals=signals)
        if copy_followup_hints:
            if pause:
                tf.pause_reason = pause
            if consent:
                tf.consent_level = consent
            if temporal:
                tf.temporal_commitment = temporal
        return tf

    return _understand, turn_idx_ref, understand_stubs


def _is_reset_turn(turn_def: dict[str, Any], inbound_text: str) -> bool:
    from sdr.domain.commands import is_reset_memory_command

    if str(turn_def.get("command") or "").strip() == "reset_memory":
        return True
    return is_reset_memory_command(inbound_text)


def _upsert_show_offer_bindings(state: Any, result: Any) -> None:
    from sdr.domain.vehicle_reference import PresentedVehicleBinding, upsert_presented_binding

    vehicles: list[dict[str, Any]] = []
    for tr in result.tool_results or []:
        if tr.get("tool") == "inventory_search":
            vehicles = list(tr.get("vehicles") or [])
            break
    if not vehicles:
        for item in getattr(result, "outbound_media", None) or []:
            vid = getattr(item, "vehicle_id", None)
            if vid:
                vehicles.append({"id": vid})
    offer = f"replay-offer-{state.thread_id}"
    seen: set[str] = set()
    position = 0
    for veh in vehicles:
        vid = str((veh or {}).get("id") or "").strip()
        if not vid or vid in seen:
            continue
        seen.add(vid)
        upsert_presented_binding(
            state,
            PresentedVehicleBinding(
                conversation_id=state.thread_id,
                provider_message_id=f"replay-img-{vid}",
                vehicle_id=vid,
                presentation_type="IMAGE",
                position=position,
                offer_set_id=offer,
            ),
        )
        position += 1


def _reset_state(state: Any) -> Any:
    from sdr.domain.types import ConversationCanonicalState, CustomerState

    return ConversationCanonicalState(
        thread_id=state.thread_id,
        customer=CustomerState(
            phone=getattr(state.customer, "phone", None),
            name=getattr(state.customer, "name", None),
        ),
    )


def _admin_event(turn_def: dict[str, Any]) -> dict[str, Any] | None:
    raw = turn_def.get("admin_event")
    return raw if isinstance(raw, dict) and raw.get("type") else None


def _apply_admin_event(state: Any, admin: dict[str, Any]) -> tuple[Any, str]:
    from sdr.domain.ownership import assume_human, resume_ai

    etype = str(admin.get("type") or "").strip().lower()
    actor = str(admin.get("actor_user_id") or "user-1")
    revision = int(getattr(state, "ownership_revision", 0) or 0)
    if etype == "assume":
        return assume_human(state, actor_user_id=actor, expected_revision=revision), "assume"
    if etype == "resume":
        reason = str(admin.get("reason") or "seller_released")
        return resume_ai(
            state,
            actor_user_id=actor,
            reason=reason,
            expected_revision=revision,
        ), "resume"
    raise ValueError(f"unknown admin_event type {etype!r}")


def _has_customer_inbound(turn_def: dict[str, Any]) -> bool:
    if str(turn_def.get("inbound") or "").strip():
        return True
    events = turn_def.get("events")
    return isinstance(events, list) and any(isinstance(e, dict) for e in events)


def _inbound_is_opt_out(inbound_text: str) -> bool:
    from sdr.domain.followup_cancel import is_opt_out_text

    return is_opt_out_text(inbound_text)


def _bot_status(state: Any) -> str:
    lifecycle = getattr(state, "lifecycle", None)
    status = getattr(lifecycle, "status", None)
    if hasattr(status, "value"):
        return str(status.value)
    return str(status or "")


def _ownership_snapshot(state: Any) -> dict[str, Any]:
    return {
        "botStatus": _bot_status(state),
        "ownershipRevision": int(getattr(state, "ownership_revision", 0) or 0),
        "assumedByUserId": getattr(state, "assumed_by_user_id", None),
        "resumedByUserId": getattr(state, "resumed_by_user_id", None),
        "resumeReason": getattr(state, "resume_reason", None),
    }


def _event_stamp(
    *,
    action: str,
    admin_event: Any = None,
    suppressed_reason: str | None = None,
    bot_status: str | None = None,
    inbound: str | None = None,
    event_kind: str | None = None,
) -> dict[str, Any]:
    from tests.golden.invariants import classify_turn_event

    payload: dict[str, Any] = {
        "action": action,
        "admin_event": admin_event,
        "suppressed_reason": suppressed_reason,
        "bot_status": bot_status,
        "inbound": inbound,
    }
    if event_kind:
        payload["event_kind"] = event_kind
    return classify_turn_event(payload)


def _synthetic_process_result(state: Any, *, reason: str, outbound: list[str] | None = None):
    from sdr.application.process_turn import ProcessTurnResult
    from sdr.domain.types import Action, ActionPlan, TurnFacts

    return ProcessTurnResult(
        action_plan=ActionPlan(action=Action.NO_REPLY, reason_code=reason, reason=reason),
        state=state,
        outbound_texts=list(outbound or []),
        turn_facts=TurnFacts(),
        tool_results=[],
    )


def _skip_dialogue_alignment(state: Any, previous_action: str) -> bool:
    if previous_action in {
        "HANDOFF_VENDOR",
        "ADMIN_ASSUME",
        "ADMIN_RESUME",
        "CLOCK_JUMP",
        "SCHEDULER_TICK",
        "FOLLOWUP_SEND",
        "INVENTORY_OVERRIDE",
        "OPT_OUT",
    }:
        return True
    return _bot_status(state) in {"HANDOFF_SENT", "HUMAN_ACTIVE", "AI_RESUMED"}


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
    from sdr.domain.types import Action
    from sdr.infrastructure.isolated_crm import IsolatedCrmStore
    from tests.golden.fixtures.seed_inventory_adapter import SEED_VERSION, seed_sha256
    from tests.golden.invariants import (
        INVARIANT_CATALOG,
        check_scenario,
        check_turn,
        collect_commercial_observations,
    )

    name = scenario.get("name", "unknown")
    turns = scenario.get("turns", [])
    state = _initial_state(scenario)
    errors: list[str] = []
    transcript: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    vendor_summary: str | None = None
    fallback_count = 0
    composer_retries = 0
    questions_rejected = 0
    crm_store = IsolatedCrmStore()
    crm_report: dict[str, Any] | None = None
    summary_validation: dict[str, Any] | None = None
    summary_llm_rejected = False
    summary_used_fallback = False
    summary_llm_attempted = False
    summary_empty_claims_rejected = False
    summary_origin = ""
    summary_used_llm = False
    dialogue_misaligned = 0
    runtime_calls = 0
    location_sends = 0
    inbound_batches: list[dict[str, Any]] = []
    commercial_observations: list[dict[str, Any]] = []
    first_inbound: str | None = None
    visual_turns = 0
    identification_source: str | None = None
    clock_iso = scenario.get("clock") or GOLDEN_CLOCK_ISO
    set_clock(clock_iso)
    from sdr.domain.clock import now_brt
    from sdr.application.followup_runtime import (
        EXECUTION_MODE_DOUBLE,
        EXECUTION_MODE_PRODUCTION,
        FollowUpRuntime,
    )
    from sdr.replay.execution_meta import replay_execution_meta
    from sdr.replay.followup_harness import FollowUpHarness, apply_clock_jump

    execution_mode = str(scenario.get("execution_mode") or EXECUTION_MODE_PRODUCTION)
    use_followup_double = execution_mode == EXECUTION_MODE_DOUBLE
    harness = FollowUpHarness(scenario_name=name, thread_id=getattr(state, "thread_id", name))
    runtime = FollowUpRuntime(conversation_id=str(getattr(state, "thread_id", name)))
    runtime.evidence.execution_mode = (
        EXECUTION_MODE_DOUBLE if use_followup_double else EXECUTION_MODE_PRODUCTION
    )
    inventory_overrides: list[dict[str, Any]] = []

    def _followup_snap() -> dict[str, Any]:
        if use_followup_double:
            return harness.snapshot()
        return runtime.replay_snapshot(runtime.last_state or state)

    def _followup_wait() -> str:
        return str(_followup_snap().get("wait_state") or "")

    def _followup_send_count() -> int:
        if use_followup_double:
            return len(harness.sends)
        return len(runtime.sends)

    async def _seed_search_with_request(_pool: Any, req: Any) -> list[Any]:
        from tests.golden.fixtures.seed_inventory_adapter import inventory_vehicles_from_seed_request

        return inventory_vehicles_from_seed_request(req)

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
        vis = getattr(search_state, "last_visual_resolution", None)
        vis_id = vis.get("matched_vehicle_id") if isinstance(vis, dict) else None
        listing_id = (
            getattr(search_state, "listing_reference", None)
            or vis_id
            or getattr(search_state, "primary_vehicle_id", None)
            or (search_state.facts or {}).get("visual_match_vehicle_id")
            or (search_state.facts or {}).get("_seed_vehicle_hint")
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
        understand, turn_idx_ref, understand_stubs = _stub_understand(
            turns, copy_followup_hints=use_followup_double
        )

    llm_calls = 0
    suppressed_outbound_count = 0
    suppressed_outbound_reasons: list[str] = []
    inbound_records: list[dict[str, Any]] = []
    events_executed: list[dict[str, Any]] = []
    crm_lead_id: str | None = None
    inner_understand = understand

    async def counting_understand(text: str, st: Any) -> Any:
        nonlocal llm_calls
        llm_calls += 1
        return await inner_understand(text, st)

    understand = counting_understand

    process_pool = pool if pool is not None else object()
    understanding_model = None
    composer_model = None
    if llm_real:
        from sdr.config import get_settings

        settings = get_settings()
        understanding_model = getattr(settings, "openai_model", None) or "gpt-4.1-mini"
        composer_model = getattr(settings, "openai_composer_model", None) or understanding_model

    def _append_control_turn(
        *,
        action: str,
        event_kind: str,
        outbound: list[str] | None = None,
        extra: dict[str, Any] | None = None,
        inbound_text: str = "",
        inbound_persisted: bool = False,
        llm_turn: int = 0,
    ) -> Any:
        outbound_texts = list(outbound or [])
        own = _ownership_snapshot(state)
        event_meta = _event_stamp(
            action=action,
            bot_status=own["botStatus"],
            inbound=inbound_text or None,
            event_kind=event_kind,
        )
        row = {
            "idx": idx,
            "inbound": inbound_text,
            "action": action,
            "outbound": outbound_texts,
            "llm_calls": llm_turn,
            "inbound_persisted": inbound_persisted,
            "bot_status": own["botStatus"],
            "ownership_revision": own["ownershipRevision"],
            "runtime_calls": 0,
            "runtime_call_count": 0,
            "wait_state": _followup_wait(),
            "followup_sends": _followup_send_count(),
            **(extra or {}),
            **event_meta,
        }
        transcript.append(row)
        traces.append(
            {
                "scenario_id": name,
                "turn_id": idx,
                "timestamp": now_brt().isoformat(),
                "timezone": "America/Sao_Paulo",
                "clock": now_brt().isoformat(),
                "botStatus": own["botStatus"],
                "ownershipRevision": own["ownershipRevision"],
                "composer_result": outbound_texts,
                "invariant_results": ["pass"],
                "llm_calls": llm_turn,
                "wait_state": _followup_wait(),
                "followup_sends": _followup_send_count(),
                "followup_tasks": runtime.task_dicts() if not use_followup_double else [t.as_dict() for t in harness.tasks],
                **(extra or {}),
                **event_meta,
            }
        )
        result = _synthetic_process_result(state, reason=event_kind, outbound=outbound_texts)
        violations = check_turn(
            scenario_name=name,
            turn_idx=idx,
            turn_def=turn_def,
            result=result,
            inbound=None,
            runtime_calls=0,
            llm_calls=llm_turn,
            inbound_persisted=inbound_persisted,
            followup=_followup_snap(),
        )
        for item in violations:
            errors.append(str(item))
        return result

    for idx, turn_def in enumerate(turns):
        turn_idx_ref[0] = idx
        handled_control = False
        override = turn_def.get("inventory_override")
        if isinstance(override, dict) and override:
            applied = (
                harness.override_inventory(override)
                if use_followup_double
                else runtime.override_inventory(override)
            )
            inventory_overrides.append(applied)
            events_executed.append({"type": "inventory_override", "turn_id": idx, **applied})
            handled_control = True
        jump = turn_def.get("clock_jump")
        if jump:
            instant = apply_clock_jump(jump)
            harness.record_clock_jump(jump, instant)
            runtime.record_clock_jump(jump, instant)
            events_executed.append(
                {"type": "clock_jump", "turn_id": idx, "clock": instant.isoformat()}
            )
            handled_control = True
        tick_spec = turn_def.get("scheduler_tick")
        tick_result = None
        if tick_spec:
            spec = tick_spec if isinstance(tick_spec, dict) else {}
            if use_followup_double:
                tick_result = harness.tick(spec)
            else:
                kind = str(spec.get("kind") or "due").lower()
                if kind == "dormant":
                    from sdr.domain.followup import apply_followup_transition, followup_decision

                    dormant_decision = followup_decision(state, inbound_text="")
                    apply_followup_transition(state, dormant_decision)
                    runtime.last_decision = dormant_decision
                    tick_result = type(
                        "Tick",
                        (),
                        {
                            "sent": [],
                            "rescheduled": [],
                            "cancelled": [],
                            "claims": [],
                        },
                    )()
                else:
                    before_sends = len(runtime.sends)
                    await runtime.tick(workers=list(spec.get("workers") or ["w1"]))
                    new_sends = runtime.sends[before_sends:]
                    tick_result = type(
                        "Tick",
                        (),
                        {
                            "sent": new_sends,
                            "rescheduled": runtime.last_tick_rescheduled,
                            "cancelled": runtime.last_tick_cancelled,
                            "claims": runtime.last_tick_claims,
                        },
                    )()
            events_executed.append(
                {
                    "type": "scheduler_tick",
                    "turn_id": idx,
                    "sent": len(tick_result.sent),
                    "rescheduled": tick_result.rescheduled,
                    "cancelled": tick_result.cancelled,
                    "claims": tick_result.claims,
                }
            )
            handled_control = True
        if turn_def.get("opt_out") and not _has_customer_inbound(turn_def):
            harness.cancel("OPT_OUT")
            await runtime.cancel("OPT_OUT")
            runtime.persist_opt_out()
            events_executed.append({"type": "opt_out", "turn_id": idx})
            handled_control = True
        if handled_control and not _has_customer_inbound(turn_def) and not _admin_event(turn_def):
            action = "CLOCK_JUMP"
            kind = "clock_jump"
            outbound: list[str] = []
            extra: dict[str, Any] = {"clock": now_brt().isoformat()}
            if override:
                action = "INVENTORY_OVERRIDE"
                kind = "inventory_override"
                extra["inventory_override"] = override
            if tick_spec:
                action = "FOLLOWUP_SEND" if tick_result and tick_result.sent else "SCHEDULER_TICK"
                kind = "scheduler_tick"
                outbound = list(tick_result.sent) if tick_result else []
                extra["scheduler_tick"] = tick_spec
                extra["rescheduled"] = list(tick_result.rescheduled) if tick_result else []
            if turn_def.get("opt_out"):
                action = "OPT_OUT"
                kind = "opt_out"
            _append_control_turn(action=action, event_kind=kind, outbound=outbound, extra=extra)
            continue
        admin = _admin_event(turn_def)
        if admin:
            try:
                state, event_name = _apply_admin_event(state, admin)
            except Exception as exc:
                errors.append(
                    f"[{name}] turn {idx}: admin_event {admin.get('type')!r} "
                    f"raised {type(exc).__name__}: {exc}"
                )
                break
            events_executed.append({"type": event_name, "turn_id": idx})
            harness.on_admin(event_name)
            runtime.on_admin(event_name, state)
            if event_name == "assume":
                await runtime.cancel("HUMAN_ASSUMED")
            if not _has_customer_inbound(turn_def):
                from sdr.application.process_turn import ProcessTurnResult
                from sdr.domain.types import Action, ActionPlan, TurnFacts

                result = ProcessTurnResult(
                    action_plan=ActionPlan(
                        action=Action.NO_REPLY,
                        reason_code=f"admin_{event_name}",
                        reason=f"Replay admin event {event_name}",
                    ),
                    state=state,
                    outbound_texts=[],
                    turn_facts=TurnFacts(),
                    tool_results=[],
                )
                own = _ownership_snapshot(state)
                admin_action = f"ADMIN_{event_name.upper()}"
                event_meta = _event_stamp(
                    action=admin_action,
                    admin_event=event_name,
                    bot_status=own["botStatus"],
                )
                transcript.append({
                    "idx": idx,
                    "inbound": "",
                    "admin_event": event_name,
                    "action": admin_action,
                    "outbound": [],
                    "llm_calls": 0,
                    "inbound_persisted": False,
                    "bot_status": own["botStatus"],
                    "ownership_revision": own["ownershipRevision"],
                    "runtime_calls": 0,
                    "runtime_call_count": 0,
                    **event_meta,
                })
                traces.append({
                    "scenario_id": name,
                    "turn_id": idx,
                    "admin_event": admin,
                    "botStatus": own["botStatus"],
                    "ownershipRevision": own["ownershipRevision"],
                    "composer_result": [],
                    "invariant_results": ["pass"],
                    "llm_calls": 0,
                    "suppressed_outbound": False,
                    "runtime_calls": 0,
                    "runtime_call_count": 0,
                    **event_meta,
                })
                violations = check_turn(
                    scenario_name=name,
                    turn_idx=idx,
                    turn_def=turn_def,
                    result=result,
                    inbound=None,
                    runtime_calls=0,
                    llm_calls=0,
                    inbound_persisted=False,
                    followup=_followup_snap(),
                )
                for v in [str(item) for item in violations]:
                    errors.append(v)
                continue

        from sdr.replay.inbound import build_replay_inbound

        inbound, image_bytes, delays = build_replay_inbound(
            turn_def,
            thread_id=state.thread_id,
            turn_idx=idx,
        )
        if image_bytes and not use_live_inventory:
            from tests.golden.fixtures.seed_inventory_adapter import seed_catalog_image_index

            ref = dict(inbound.raw_message_ref or {})
            if not ref.get("image_index") and not ref.get("fingerprints"):
                ref["image_index"] = seed_catalog_image_index()
                inbound.raw_message_ref = ref
        inbound_text = inbound.effective_text or str(turn_def.get("inbound") or "")
        listing_id = turn_def.get("listing_id")
        listing_url = turn_def.get("listing_url")
        alignment: dict[str, Any] = {
            "expected_question_field": None,
            "detected_question_field": None,
            "next_customer_response_type": turn_def.get("responds_to_field")
            or turn_def.get("response_mode"),
            "dialogue_alignment": True,
        }
        if idx > 0 and traces and not _skip_dialogue_alignment(
            state,
            str((transcript[-1].get("action") if transcript else "") or "").upper(),
        ) and not _inbound_is_opt_out(inbound_text) and not _is_reset_turn(turn_def, inbound_text):
            from sdr.domain.dialogue_alignment import evaluate_dialogue_alignment

            prev = traces[-1]
            prev_adherence = prev.get("question_adherence") or {}
            alignment = evaluate_dialogue_alignment(
                expected_question_field=prev_adherence.get("expected_question_field")
                or prev.get("ask_field"),
                detected_question_field=prev_adherence.get("detected_question_field"),
                inbound=inbound_text,
                turn_def=turn_def,
            )
            prev["next_customer_response_type"] = alignment.get("next_customer_response_type")
            prev["dialogue_alignment"] = alignment.get("dialogue_alignment")
            if not alignment.get("dialogue_alignment"):
                dialogue_misaligned += 1
                errors.append(
                    f"[{name}] turn {idx}: dialogue_alignment — "
                    f"asked {alignment.get('detected_question_field') or alignment.get('expected_question_field')!r} "
                    f"but inbound {inbound_text!r} "
                    f"(type={alignment.get('next_customer_response_type')!r})"
                )
                traces.append({
                    "scenario_id": name,
                    "turn_id": idx,
                    "customer_message": inbound_text,
                    "dialogue_alignment": alignment,
                    "invariant_results": ["dialogue_misaligned"],
                })
                break
        state_before = {
            "intent": state.intent.value if hasattr(state.intent, "value") else str(state.intent),
            "facts": dict(state.facts),
            "missing_fields": list(state.missing_fields or []),
            "deferred_fields": list(state.deferred_fields or []),
            "collected_fields": list(state.collected_fields or []),
            "visit_preferred_time": state.visit_preferred_time,
        }
        if listing_id or listing_url:
            ref = dict(inbound.raw_message_ref or {})
            if listing_id:
                ref["listing_id"] = listing_id
            if listing_url:
                ref["listing_url"] = listing_url
            inbound.raw_message_ref = ref
        if show_trace:
            print(f"\n{'='*60}")
            print(f"  Turn {idx}: {inbound_text!r}")
            print(f"  listing_id: {listing_id}")
            print(f"  segments: {(inbound.raw_message_ref or {}).get('segment_count')}")
            print(f"  assistant_turn_count: {state.assistant_turn_count}")
            print(f"  State facts before: {dict(state.facts)}")

        started = time.perf_counter()
        runtime_calls += 1
        inbound_batches.append(
            {
                "turn_id": idx,
                "batch_id": (inbound.raw_message_ref or {}).get("batch_id"),
                "segment_count": (inbound.raw_message_ref or {}).get("segment_count")
                or len(inbound.segments or [])
                or 1,
                "delays_ms": delays,
                "quoted": [
                    {"stanza_id": q.stanza_id, "quoted_text": q.quoted_text}
                    for q in (inbound.quoted or [])
                ],
                "content_type": inbound.content_type.value
                if hasattr(inbound.content_type, "value")
                else str(inbound.content_type),
                "runtime_calls": 1,
            }
        )
        if first_inbound is None and not _is_reset_turn(turn_def, inbound_text):
            first_inbound = inbound_text
        if inbound_text and not _is_reset_turn(turn_def, inbound_text):
            from sdr.domain.conversation_revision import bump_context_revision

            bump_context_revision(state)
        inbound_record = {
            "turn_id": idx,
            "text": inbound_text,
            "persisted": True,
            "bot_status": _bot_status(state),
        }
        inbound_records.append(inbound_record)
        llm_before = llm_calls
        if (
            not use_followup_double
            and not _is_reset_turn(turn_def, inbound_text)
            and runtime.has_pending()
        ):
            from sdr.domain.followup import resume_after_customer_reply

            if _inbound_is_opt_out(inbound_text):
                await runtime.cancel("OPT_OUT")
                runtime.persist_opt_out(state)
            else:
                await runtime.cancel("CUSTOMER_REPLIED")
                resume_after_customer_reply(state)
        try:
            if _is_reset_turn(turn_def, inbound_text):
                from sdr.application.process_turn import ProcessTurnResult
                from sdr.domain.commands import RESET_MEMORY_CONFIRMATION_PT
                from sdr.domain.types import Action, ActionPlan, TurnFacts

                state = _reset_state(state)
                harness.on_reset()
                await runtime.on_reset()
                runtime.stamp_opt_out_on_state(state)
                runtime.last_state = state
                result = ProcessTurnResult(
                    action_plan=ActionPlan(
                        action=Action.NO_REPLY,
                        reason_code="reset_memory",
                        reason="Isolated /deletar command",
                    ),
                    state=state,
                    outbound_texts=[RESET_MEMORY_CONFIRMATION_PT],
                    turn_facts=TurnFacts(),
                    tool_results=[],
                )
            elif _bot_status(state) == "HUMAN_ACTIVE":
                from sdr.application.process_turn import ProcessTurnResult
                from sdr.domain.types import Action, ActionPlan, TurnFacts

                result = ProcessTurnResult(
                    action_plan=ActionPlan(
                        action=Action.NO_REPLY,
                        reason_code="ai_silenced",
                        reason="HUMAN_ACTIVE ownership — Júlia silent",
                    ),
                    state=state,
                    outbound_texts=[],
                    turn_facts=TurnFacts(),
                    tool_results=[],
                )
            elif (not use_followup_double) and _inbound_is_opt_out(inbound_text):
                from sdr.application.process_turn import ProcessTurnResult
                from sdr.domain.types import Action, ActionPlan, TurnFacts

                runtime.apply_policy(state, inbound_text)
                await runtime.cancel("OPT_OUT")
                runtime.persist_opt_out(state)
                events_executed.append({"type": "opt_out", "turn_id": idx})
                result = ProcessTurnResult(
                    action_plan=ActionPlan(
                        action=Action.NO_REPLY,
                        reason_code="opt_out",
                        reason="Customer opt-out",
                    ),
                    state=state,
                    outbound_texts=[],
                    turn_facts=TurnFacts(),
                    tool_results=[],
                )
            elif turn_def.get("opt_out") and use_followup_double:
                from sdr.application.process_turn import ProcessTurnResult
                from sdr.domain.types import Action, ActionPlan, TurnFacts

                harness.cancel("OPT_OUT")
                events_executed.append({"type": "opt_out", "turn_id": idx})
                result = ProcessTurnResult(
                    action_plan=ActionPlan(
                        action=Action.NO_REPLY,
                        reason_code="opt_out",
                        reason="Customer opt-out",
                    ),
                    state=state,
                    outbound_texts=[],
                    turn_facts=TurnFacts(),
                    tool_results=[],
                )
            elif (
                use_followup_double
                and isinstance(turn_def.get("followup"), dict)
                and turn_def["followup"].get("schedule")
                and not llm_real
                and turn_def["followup"].get("runtime") is not True
            ):
                from sdr.application.process_turn import ProcessTurnResult
                from sdr.domain.types import Action, ActionPlan, BusinessIntent, TurnFacts

                stub = turn_def.get("understand_return") or {}
                intent_raw = str(stub.get("intent") or "purchase_financing").lower()
                try:
                    intent = BusinessIntent(intent_raw)
                except ValueError:
                    intent = BusinessIntent.PURCHASE_FINANCING
                facts = dict(stub.get("facts") or {})
                if facts:
                    state.facts.update({k: v for k, v in facts.items() if v is not None})
                state.intent = intent
                state.assistant_turn_count = int(getattr(state, "assistant_turn_count", 0) or 0) + 1
                ack = (
                    "Certo. Te chamo no horário combinado."
                    if turn_def["followup"].get("consent_level") == "EXPLICIT_WITH_TIME"
                    else "Certo. Posso te chamar no próximo dia útil para saber o que decidiram?"
                )
                result = ProcessTurnResult(
                    action_plan=ActionPlan(
                        action=Action.ASK_INFO,
                        reason_code="followup_pause_ack",
                        reason="Deterministic pause acknowledgment for follow-up replay",
                    ),
                    state=state,
                    outbound_texts=[ack],
                    turn_facts=TurnFacts(intent=intent, facts=facts),
                    tool_results=[],
                )
            else:
                with contextlib.ExitStack() as stack:
                    if not use_live_inventory:
                        stack.enter_context(
                            mock.patch.dict(
                                "sdr.application.tool_executor._TOOL_REGISTRY",
                                {"inventory_search": _seed_run_inventory_search},
                            )
                        )
                        stack.enter_context(
                            mock.patch(
                                "sdr.tools.inventory.search_with_request",
                                _seed_search_with_request,
                            )
                        )
                    result = await process_turn(
                        state=state,
                        inbound=inbound,
                        inbound_text=inbound_text,
                        understand=understand,
                        pool=process_pool,
                        image_bytes=image_bytes,
                    )
                _upsert_show_offer_bindings(result.state, result)
                if not use_followup_double:
                    runtime.apply_policy(
                        result.state, inbound_text, result.turn_facts
                    )
                    await runtime.sync_task(result.state, inbound_text)
                    runtime.last_state = result.state
        except Exception as exc:
            errors.append(f"[{name}] turn {idx}: process_turn raised {type(exc).__name__}: {exc}")
            break
        latency_ms = int((time.perf_counter() - started) * 1000)
        if not _is_reset_turn(turn_def, inbound_text) and not turn_def.get("opt_out"):
            harness.after_customer_inbound(
                turn_def,
                ownership_revision=int(getattr(result.state, "ownership_revision", 0) or 0),
            )

        if getattr(result, "outbound_location", None):
            location_sends += 1
        vis = getattr(result.state, "last_visual_resolution", None) or {}
        ctype = (
            inbound.content_type.value
            if hasattr(inbound.content_type, "value")
            else str(inbound.content_type)
        )
        if image_bytes or str(ctype).upper() == "IMAGE":
            visual_turns += 1
            if isinstance(vis, dict) and vis.get("resolution_source"):
                identification_source = vis.get("resolution_source")

        plan = result.action_plan
        action_val = plan.action.value if hasattr(plan.action, "value") else str(plan.action)
        action_upper = str(action_val or "").upper()
        turn_llm_calls = llm_calls - llm_before
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
        composer_retries += int(getattr(result, "composer_retries", 0) or 0)
        questions_rejected += int(getattr(result, "questions_rejected", 0) or 0)
        adherence = getattr(result, "question_adherence", None) or {}
        suppressed_reason = None
        if action_upper == "NO_REPLY" and str(plan.reason_code or "") in {
            "ai_silenced",
            "human_or_handoff_silence",
            "human_active",
        }:
            suppressed_reason = str(plan.reason_code)
            suppressed_outbound_count += 1
            suppressed_outbound_reasons.append(suppressed_reason)
        event_meta = _event_stamp(
            action=action_upper,
            suppressed_reason=suppressed_reason,
            bot_status=_bot_status(result.state),
            inbound=inbound_text,
        )
        if event_meta["outbound_expected"] and not (result.outbound_texts or []):
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
            "turn_intent": result.turn_facts.intent.value if result.turn_facts else None,
            "canonical_intent": result.state.intent.value,
            "conversation_intent": result.state.intent.value,
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
            "question_adherence": adherence,
            "dialogue_alignment": alignment,
            "runtime_calls": 1,
            "runtime_call_count": 1,
            "segment_count": (inbound.raw_message_ref or {}).get("segment_count"),
            "primary_vehicle_id": result.state.primary_vehicle_id,
            "llm_calls": turn_llm_calls,
            "inbound_persisted": True,
            "bot_status": _bot_status(result.state),
            "ownership_revision": int(getattr(result.state, "ownership_revision", 0) or 0),
            "suppressed_reason": suppressed_reason,
            "wait_state": _followup_wait(),
            "followup_sends": _followup_send_count(),
            **event_meta,
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
            "turn_intent": result.turn_facts.intent.value if result.turn_facts else None,
            "final_intent": result.state.intent.value,
            "conversation_intent": result.state.intent.value,
            "canonical_intent": result.state.intent.value,
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
                "primary_vehicle_id": result.state.primary_vehicle_id,
                "location_sent": bool(getattr(result.state, "location_sent", False)),
                "document_received": bool(getattr(result.state, "document_received", False)),
                "botStatus": _bot_status(result.state),
                "ownershipRevision": int(getattr(result.state, "ownership_revision", 0) or 0),
            },
            "applicable_fields": list(result.state.collected_fields or [])
            + list(result.state.missing_fields or []),
            "missing_fields": list(result.state.missing_fields or []),
            "deferred_fields": list(result.state.deferred_fields or []),
            "action_plan": {
                "action": action_val,
                "reason_code": plan.reason_code,
                "handoff": plan.handoff,
                "primary_action": getattr(plan, "primary_action", None),
                "supporting_acts": list(getattr(plan, "supporting_acts", None) or []),
                "forbidden_concurrent_actions": list(
                    getattr(plan, "forbidden_concurrent_actions", None) or []
                ),
            },
            "qualification_trace": dict(getattr(plan, "qualification_trace", None) or {}),
            "ask_field": plan.ask_field,
            "question_adherence": adherence,
            "dialogue_alignment": alignment,
            "tool_calls": plan.tool_calls,
            "tool_results": result.tool_results,
            "inventory_query": inv_tr.get("search_params"),
            "inventory_match": result.state.last_inventory_match,
            "composer_result": list(result.outbound_texts or []),
            "vehicle_cards": vehicle_cards,
            "outbound_media": media_items,
            "composer_model": composer_model if llm_real else "template/stub",
            "retry": int(getattr(result, "composer_retries", 0) or 0),
            "questions_rejected": int(getattr(result, "questions_rejected", 0) or 0),
            "fallback": fallback_used,
            "validations": validator,
            "latency_ms": latency_ms,
            "handoff_reason": result.state.lifecycle.handoff_reason,
            "botStatus": _bot_status(result.state),
            "ownershipRevision": int(getattr(result.state, "ownership_revision", 0) or 0),
            "llm_calls": turn_llm_calls,
            "suppressed_outbound": bool(suppressed_reason),
            "suppressed_reason": suppressed_reason,
            "inbound_persisted": True,
            "runtime_call_count": 1,
            **event_meta,
        }
        traces.append(trace_row)
        if show_trace:
            if not llm_real and idx < len(understand_stubs):
                print(f"  Stub understand: intent={understand_stubs[idx].get('intent', 'UNKNOWN')}")
            else:
                print(
                    f"  Understand: turn_intent={result.turn_facts.intent.value} "
                    f"canonical_intent={result.state.intent.value} facts={facts_out}"
                )
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
            inbound=inbound,
            runtime_calls=1,
            llm_calls=turn_llm_calls,
            inbound_persisted=True,
            suppressed_reason=suppressed_reason,
            followup=_followup_snap(),
        )
        inv_msgs = [str(v) for v in violations]
        for v in inv_msgs:
            errors.append(v)
        obs = collect_commercial_observations(
            scenario=scenario,
            result=result,
            turn_def=turn_def,
            outbound_joined=" ".join(result.outbound_texts or []),
            action=action_val,
        )
        if obs:
            commercial_observations.extend({"turn": idx, **item} for item in obs)
        trace_row["invariant_results"] = inv_msgs or ["pass"]
        trace_row["commercial_observations"] = obs
        trace_row["runtime_calls"] = 1
        trace_row["inbound_batch"] = inbound_batches[-1]

        is_handoff = plan.action == Action.HANDOFF_VENDOR or plan.handoff
        if is_handoff:
            events_executed.append({"type": "handoff", "turn_id": idx})
            from sdr.domain.vendor_summary import compose_vendor_summary

            composed = None
            try:
                composed = compose_vendor_summary(result.state)
                vendor_summary = composed.text
                summary_validation = composed.validation
                summary_llm_rejected = composed.llm_rejected
                summary_used_fallback = composed.used_fallback
                summary_llm_attempted = bool(getattr(composed, "llm_attempted", False))
                summary_empty_claims_rejected = bool(
                    getattr(composed, "empty_claims_rejected", False)
                )
                summary_origin = composed.origin
                summary_used_llm = bool(composed.used_llm)
            except Exception as exc:
                vendor_summary = f"(summary failed: {exc})"
                summary_validation = {"pass": False, "violations": [str(exc)]}
                summary_llm_rejected = False
                summary_used_fallback = True
                summary_origin = "error"
            result.state.crm_revision = int(getattr(result.state, "crm_revision", 0) or 0) + 1
            if result.state.active_lead_ids:
                stored = crm_store.sync_from_state(
                    result.state.active_lead_ids[0],
                    result.state,
                    qualify=True,
                    first_inbound=first_inbound,
                )
            else:
                stored = crm_store.persist_handoff(
                    result.state,
                    composed=composed,
                    first_inbound=first_inbound,
                )
                result.state.active_lead_ids = [str(stored["id"])]
            crm_lead_id = str(stored["id"])
            crm_report = crm_store.verify(result.state.thread_id)
            trace_row["crm_payload"] = stored
            trace_row["crm_persist"] = crm_report
            trace_row["summary_validation"] = summary_validation
            if composed is not None:
                trace_row["summary_propositions"] = getattr(composed, "propositions", None)
                trace_row["summary_claims"] = (summary_validation or {}).get("claims")
            if summary_validation and not summary_validation.get("pass"):
                errors.append(
                    f"[{name}] turn {idx}: summary_validation — {summary_validation.get('violations')}"
                )
            if show_trace:
                print(f"  CRM juliaSummary: {vendor_summary}")
                print(f"  CRM persist verified: {crm_report.get('matches_payload')}")
                print(f"  summary_validation: {summary_validation}")
        elif result.state.active_lead_ids:
            result.state.crm_revision = int(getattr(result.state, "crm_revision", 0) or 0) + 1
            stored = crm_store.sync_from_state(
                result.state.active_lead_ids[0],
                result.state,
                qualify=False,
                first_inbound=first_inbound,
            )
            crm_lead_id = str(stored["id"])
            crm_report = crm_store.verify(result.state.thread_id)
            trace_row["crm_payload"] = stored
            trace_row["crm_persist"] = crm_report

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
    handoff_seen = any(
        str(t.get("action") or "").upper() == "HANDOFF_VENDOR" for t in transcript
    )
    if _followup_wait() == "DORMANT":
        obtained_terminal = "DORMANT"
    elif _followup_send_count():
        obtained_terminal = "FOLLOWUP_SENT"
    elif handoff_seen:
        obtained_terminal = "HANDOFF_VENDOR"
    elif transcript:
        last_action = (transcript[-1].get("action") or "").upper()
        if last_action in {"NO_REPLY", "ADMIN_ASSUME", "OPT_OUT"}:
            obtained_terminal = "SILENCE"
        elif last_action.startswith("ADMIN_"):
            obtained_terminal = last_action
        else:
            obtained_terminal = last_action

    own_final = _ownership_snapshot(state)
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
        retry_count=composer_retries,
        composer_retries=composer_retries,
        questions_rejected=questions_rejected,
        traces=traces,
        clock_iso=clock_iso,
        seed_version=SEED_VERSION,
        understanding_model=understanding_model,
        composer_model=composer_model,
        summary_validation=summary_validation,
        summary_llm_rejected=summary_llm_rejected,
        summary_used_fallback=summary_used_fallback,
        summary_llm_attempted=summary_llm_attempted,
        summary_empty_claims_rejected=summary_empty_claims_rejected,
        summary_origin=summary_origin,
        summary_used_llm=summary_used_llm,
        dialogue_misaligned=dialogue_misaligned,
        invariants_executed=list(INVARIANT_CATALOG),
        runtime_calls=runtime_calls,
        location_sends=location_sends,
        inbound_batches=inbound_batches,
        commercial_observations=commercial_observations,
        seed_sha256=seed_sha256(),
        inventory_source="seed_isolated",
        identification_source=identification_source,
        first_inbound=first_inbound,
        visual_turns=visual_turns,
        llm_calls=llm_calls,
        suppressed_outbound_count=suppressed_outbound_count,
        suppressed_outbound_reasons=list(suppressed_outbound_reasons),
        inbound_persisted=list(inbound_records),
        events_executed=list(events_executed),
        crm_handoff_count=int(crm_store.handoff_count),
        crm_lead_id=crm_lead_id,
        bot_status=own_final["botStatus"],
        ownership_revision=int(own_final["ownershipRevision"]),
        followup_tasks=runtime.task_dicts() if not use_followup_double else [t.as_dict() for t in harness.tasks],
        followup_sends=_followup_send_count(),
        followup_composer_calls=(
            runtime.composer_calls if not use_followup_double else harness.composer_calls
        ),
        wait_state=_followup_wait(),
        clock_jumps=list(runtime.clock_jumps if not use_followup_double else harness.clock_jumps),
        followup_cancels=list(runtime.cancels if not use_followup_double else harness.cancels),
        followup_claims=list(runtime.claims if not use_followup_double else harness.claims),
        followup_transitions=list(
            runtime.transitions if not use_followup_double else harness.transitions
        ),
        inventory_overrides=list(inventory_overrides),
        idempotency_keys=(
            [t.get("idempotencyKey") for t in runtime.task_dicts() if t.get("idempotencyKey")]
            if not use_followup_double
            else [t.idempotency_key for t in harness.tasks]
        ),
        execution_mode=execution_mode,
        followup_evidence=runtime.evidence.as_dict(),
        execution_meta=replay_execution_meta(
            scenario_execution_mode=execution_mode,
            use_followup_double=use_followup_double,
            llm_real=llm_real,
        ).as_dict(),
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
        kind = str(turn.get("event_kind") or "")
        if kind == "clock_jump" or turn.get("action") == "CLOCK_JUMP":
            lines.append(f"**Clock jump:** {turn.get('clock') or result.clock_iso}")
            lines.append(f"_wait={turn.get('wait_state')} · sends={turn.get('followup_sends')}_")
            lines.append("")
            continue
        if kind == "scheduler_tick" or str(turn.get("action") or "").startswith("FOLLOWUP") or turn.get("action") == "SCHEDULER_TICK":
            lines.append(f"**Scheduler:** {turn.get('action')}")
            for bubble in turn.get("outbound") or []:
                lines.append(f"**Júlia:** {bubble}")
            if not (turn.get("outbound") or []):
                lines.append("**Júlia:** _(sem follow-up)_")
            lines.append(f"_wait={turn.get('wait_state')} · sends={turn.get('followup_sends')}_")
            lines.append("")
            continue
        if kind == "inventory_override" or turn.get("action") == "INVENTORY_OVERRIDE":
            lines.append(f"**Inventory:** {turn.get('inventory_override')}")
            lines.append("")
            continue
        lines.append(f"**Cliente:** {turn['inbound']}")
        outbound = list(turn.get("outbound") or [])
        cards = list(turn.get("vehicle_cards") or [])
        media = list(turn.get("outbound_media") or [])
        # Match WhatsApp send order for SHOW_OFFERS: context → card/media → question.
        if cards or media:
            leading = outbound[:1]
            trailing = outbound[1:]
        else:
            leading = outbound
            trailing = []
        for bubble in leading:
            lines.append(f"**Júlia:** {bubble}")
        for card in cards:
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
        for media_item in media:
            cap = (media_item.get("caption") or "").strip()
            url = media_item.get("url") or ""
            if url and url not in " ".join(lines[-8:]):
                lines.append(f"**Mídia:** {media_item.get('mediatype') or 'image'} {url}")
            if cap:
                lines.append(f"**Caption:** {cap}")
        for bubble in trailing:
            lines.append(f"**Júlia:** {bubble}")
        if not outbound and not cards:
            lines.append("**Júlia:** _(sem resposta)_")
        meta = []
        if turn.get("action"):
            meta.append(turn["action"])
        if turn.get("ask_field"):
            meta.append(f"ask={turn['ask_field']}")
        turn_intent = turn.get("turn_intent") or turn.get("intent")
        canonical = turn.get("canonical_intent") or turn.get("conversation_intent")
        if turn_intent:
            meta.append(f"turn_intent={turn_intent}")
        if canonical:
            meta.append(f"canonical_intent={canonical}")
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


def write_transcripts(results: list[ScenarioRunResult], *, output_dir: Path | None = None) -> Path:
    dest = output_dir or _TRANSCRIPTS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "latest.md"
    chunks = ["# Golden scenarios — histórico bruto\n"]
    for r in results:
        chunks.append(format_conversation(r))
        chunks.append("---\n")
    path.write_text("\n".join(chunks), encoding="utf-8")
    traces_dir = dest / "traces"
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
            "summary_origin": r.summary_origin,
            "persist": r.crm_report,
            "technical_status": r.technical_status,
            "obtained_terminal": r.obtained_terminal,
            "runtime_calls": r.runtime_calls,
            "inbound_batches": r.inbound_batches,
            "commercial_observations": r.commercial_observations,
            "identification_source": r.identification_source,
            "human_review": "PENDING_HUMAN_REVIEW",
        })
        from sdr.replay.artifacts import human_rubric_markdown

        (dest / f"rubric_{r.name}.md").write_text(human_rubric_markdown(r.name), encoding="utf-8")
    (dest / "crm_persist.json").write_text(
        json.dumps(crm_rows, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    from sdr.replay.round_report import build_round_report

    report = build_round_report(results)
    (dest / "round_report.json").write_text(
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
    repeat = 1
    run_id = None
    filtered: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--repeat" and i + 1 < len(argv):
            repeat = max(1, int(argv[i + 1]))
            i += 2
            continue
        if arg.startswith("--repeat="):
            repeat = max(1, int(arg.split("=", 1)[1]))
            i += 1
            continue
        if arg == "--run-id" and i + 1 < len(argv):
            run_id = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--run-id="):
            run_id = arg.split("=", 1)[1]
            i += 1
            continue
        if not arg.startswith("-"):
            filtered.append(arg)
        i += 1
    names = filtered

    if not run_all and not names:
        print("Usage: python -m sdr.replay <scenario_name|path> [--show-trace] [--llm-real]")
        print("       python -m sdr.replay --all [--show-trace] [--llm-real]")
        print("       python -m sdr.replay --llm-real --repeat 3 <scenario> [<scenario>...]")
        return 1

    if llm_real:
        from sdr.replay.artifacts import restore_openai_key

        if not restore_openai_key():
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
        for rep in range(repeat):
            run = await run_scenario_detailed(
                scenario,
                show_trace=show_trace or llm_real,
                pool=live_pool,
                llm_real=llm_real,
                use_live_inventory=use_live_inventory,
            )
            key = run.name if repeat == 1 else f"{run.name}__rep{rep + 1}"
            if repeat > 1:
                run.name = key
            results[key] = run
            ordered.append(run)
            if llm_real:
                print("\n" + format_conversation(run))

    _print_report(results)
    if llm_real:
        from datetime import datetime

        from tests.golden.fixtures.seed_inventory_adapter import SEED_VERSION, seed_sha256
        from sdr.replay.artifacts import GATE_ROOT, git_head, new_run_id, write_meta

        rid = run_id or new_run_id()
        dest = GATE_ROOT / rid
        meta = {
            "run_id": rid,
            "commit": git_head(),
            "started_at": datetime.now().isoformat(),
            "timezone": "America/Sao_Paulo",
            "clock": ordered[0].clock_iso if ordered else None,
            "models": {
                "understanding": ordered[0].understanding_model if ordered else None,
                "composer": ordered[0].composer_model if ordered else None,
                "summary_llm": False,
            },
            "inventory": {
                "source": "seed_isolated",
                "seed_version": SEED_VERSION,
                "seed_sha256": seed_sha256(),
                "remote_consulted": False,
            },
            "repeat": repeat,
            "scenario_count": len(ordered),
        }
        write_meta(dest, meta)
        path = write_transcripts(ordered, output_dir=dest)
        write_transcripts(ordered, output_dir=_TRANSCRIPTS_DIR)
        print(f"\nTranscripts written to {path}")
        print(f"Run directory: {dest}")
    failed_count = sum(1 for r in results.values() if not r.ok)
    return 0 if failed_count == 0 else 1


def main() -> None:
    """Entry point for `python -m sdr.replay`."""
    logging.basicConfig(level=logging.WARNING)
    argv = sys.argv[1:]
    sys.exit(asyncio.run(_main(argv)))


if __name__ == "__main__":
    main()
