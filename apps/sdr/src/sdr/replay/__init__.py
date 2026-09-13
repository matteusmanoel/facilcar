"""replay package — public API."""

from __future__ import annotations

from typing import Any, Callable


def _make_deterministic_understand(
    turns: list[dict[str, Any]],
) -> tuple[Callable, list[dict[str, Any]]]:
    """Build a deterministic ``understand`` stub from a YAML-format turn list.

    Each turn may contain an ``understanding`` block with:
        intent, language, facts_entries (list of {key, value}),
        signals (dict), confidence_entries (list of {key, value}).

    Returns:
        (understand_coroutine, stubs_list)
    """
    from sdr.domain.types import BusinessIntent, HandoffSignals, TurnFacts

    stubs: list[dict[str, Any]] = []
    for turn in turns:
        if turn.get("role") != "customer":
            continue
        if turn.get("command") == "reset_memory":
            continue
        u = turn.get("understanding") or {}
        stubs.append(u)

    idx_ref: list[int] = [0]

    async def _understand(text: str, state: Any) -> TurnFacts:
        idx = idx_ref[0]
        stub = stubs[idx] if idx < len(stubs) else {}
        idx_ref[0] += 1

        intent_str = stub.get("intent", "unknown")
        try:
            intent = BusinessIntent(intent_str.lower())
        except ValueError:
            intent = BusinessIntent.UNKNOWN

        language = stub.get("language")

        facts: dict[str, Any] = {}
        for entry in stub.get("facts_entries") or []:
            key = entry["key"]
            value = entry["value"]
            if key in {"desired_engine_flexible", "desired_engine_any"} and isinstance(value, str):
                value = value.strip().lower() in {"true", "1", "yes", "sim"}
            facts[key] = value

        signals_raw = stub.get("signals") or {}
        valid_fields = {f.name for f in HandoffSignals.__dataclass_fields__.values()}
        signals = HandoffSignals(**{k: v for k, v in signals_raw.items() if k in valid_fields and v is not None})

        confidence: dict[str, float] = {}
        for entry in stub.get("confidence_entries") or []:
            confidence[entry["key"]] = float(entry["value"])

        photo_request = stub.get("photo_request") or None

        # Handle alternative_scope, budget_status, pending_resolution
        from sdr.domain.types import AlternativeScope, BudgetStatus, PendingResolution
        alt_scope_raw = stub.get("alternative_scope")
        alt_scope = None
        if alt_scope_raw:
            try:
                alt_scope = AlternativeScope(alt_scope_raw.upper())
            except (ValueError, AttributeError):
                pass

        budget_status_raw = stub.get("budget_status")
        budget_status = None
        if budget_status_raw:
            try:
                budget_status = BudgetStatus(budget_status_raw.upper())
            except (ValueError, AttributeError):
                pass

        pending_resolution_raw = stub.get("pending_resolution")
        pending_resolution = None
        if pending_resolution_raw:
            try:
                pending_resolution = PendingResolution(pending_resolution_raw.upper())
            except (ValueError, AttributeError):
                pass

        return TurnFacts(
            intent=intent,
            language=language,
            facts=facts,
            signals=signals,
            confidence=confidence,
            photo_request=photo_request,
            alternative_scope=alt_scope,
            budget_status=budget_status,
            pending_resolution=pending_resolution,
        )

    return _understand, stubs


def _facts_equal(actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    if isinstance(actual, (list, tuple)):
        if isinstance(expected, (list, tuple)):
            return len(actual) == len(expected) and all(
                _facts_equal(a, e) for a, e in zip(actual, expected)
            )
        return any(_facts_equal(item, expected) for item in actual)
    if str(actual).lower() == str(expected).lower():
        return True
    try:
        return float(actual) == float(expected)
    except (TypeError, ValueError):
        return False


def _check_turn_assertions(
    customer_turn: int,
    ta: dict[str, Any],
    result: Any,
    before: Any,
) -> list[str]:
    """Check turn_assertions from YAML scenario against a ProcessTurnResult.

    Returns list of failure strings (empty = pass).
    """
    failures: list[str] = []
    plan = result.action_plan
    state = result.state
    outbound = " ".join(result.outbound_texts or []).lower()
    prefix = f"turn {customer_turn}"

    intent_expected = ta.get("intent")
    if intent_expected and state.intent.value != intent_expected.lower():
        failures.append(
            f"{prefix}: intent expected {intent_expected!r}, got {state.intent.value!r}"
        )

    action_not = ta.get("action_not")
    if action_not:
        got_action = plan.action.value if hasattr(plan.action, "value") else str(plan.action)
        if got_action.lower() == action_not.lower():
            failures.append(
                f"{prefix}: action should not be {action_not!r}, but it is"
            )

    reason_not = ta.get("reason_not")
    if reason_not and hasattr(plan, "reason_code"):
        got_reason = plan.reason_code or ""
        if reason_not.lower() in got_reason.lower():
            failures.append(
                f"{prefix}: reason_code should not contain {reason_not!r}, got {got_reason!r}"
            )

    facts_include = ta.get("facts_include") or {}
    for k, v in facts_include.items():
        actual = state.facts.get(k)
        if not _facts_equal(actual, v):
            failures.append(f"{prefix}: expected facts[{k!r}]={v!r}, got {actual!r}")

    prior_facts = ta.get("prior_facts_preserved") or {}
    for k, v in prior_facts.items():
        actual = state.facts.get(k)
        if not _facts_equal(actual, v):
            failures.append(f"{prefix}: prior fact {k!r}={v!r} was lost; got {actual!r}")

    if ta.get("inventory_outcome"):
        expected_out = ta["inventory_outcome"]
        actual_out = None
        for tr in result.tool_results:
            if tr.get("tool") == "inventory_search":
                actual_out = tr.get("outcome")
                break
        if actual_out != expected_out:
            failures.append(
                f"{prefix}: expected inventory_outcome={expected_out!r}, got {actual_out!r}"
            )

    if ta.get("search_key_changed"):
        if state.last_inventory_search_key == getattr(before, "last_inventory_search_key", None):
            failures.append(
                f"{prefix}: expected inventory search key to change; "
                f"got {state.last_inventory_search_key!r}"
            )

    no_greeting = ta.get("no_greeting_in_response")
    if no_greeting:
        for phrase in ("sou a júlia", "sou júlia", "aqui é a júlia"):
            if phrase in outbound:
                failures.append(
                    f"{prefix}: greeting phrase {phrase!r} found in outbound"
                )

    if ta.get("no_generic_restart"):
        for phrase in (
            "como posso te ajudar hoje",
            "como posso ajudar você hoje",
            "como posso ajudar",
            "em que posso te ajudar",
        ):
            if phrase in outbound:
                failures.append(f"{prefix}: generic restart {phrase!r} found in outbound")

    return failures


def inbound_from_fixture_turn(
    turn: dict[str, Any],
    text: str,
    thread_id: str,
) -> Any | None:
    """Build an InboundTurn from a fixture turn definition, or return None for plain text.

    Returns InboundTurn when the turn specifies media / status overrides.
    Returns None to let process_turn use inbound_text=text directly.
    """
    from sdr.domain.inbound import ContentType, InboundTurn, MediaFailureCode, MediaStatus

    media = turn.get("media") or {}
    if not media:
        return None

    content_type_str = media.get("content_type", "TEXT").upper()
    try:
        ct = ContentType[content_type_str]
    except KeyError:
        ct = ContentType.TEXT

    media_status_str = media.get("status", "NONE").upper()
    try:
        ms = MediaStatus[media_status_str]
    except KeyError:
        ms = MediaStatus.NONE

    failure_code_str = media.get("failure_code")
    fc = None
    if failure_code_str:
        try:
            fc = MediaFailureCode[failure_code_str.upper()]
        except KeyError:
            pass

    return InboundTurn(
        thread_id=thread_id,
        content_type=ct,
        text=text if text else None,
        media_status=ms,
        failure_code=fc,
    )


async def run_replay(
    fixture_path: str,
    *,
    mode: str = "deterministic",
    with_db: bool = False,
    pool: Any = None,
) -> bool:
    """Run a YAML fixture file end-to-end in deterministic mode.

    ``with_db`` opts into passing a DB pool to ``process_turn``. When ``pool``
    is already provided, it is used as-is (no implicit connection). When
    ``with_db=True`` and ``pool is None``, a pool is initialized from settings.
    Default ``with_db=False`` never opens a remote connection.
    """
    from pathlib import Path

    import yaml

    from sdr.application.process_turn import process_turn
    from sdr.domain.types import ConversationCanonicalState, CustomerState

    path = _resolve_fixture(fixture_path)
    data = yaml.safe_load(Path(path).read_text())
    turns = data["turns"]
    understand, _ = _make_deterministic_understand(turns)
    state = ConversationCanonicalState(
        thread_id=f"replay_{Path(path).stem}",
        customer=CustomerState(phone="5541999999999"),
    )

    turn_assertions: dict[int, dict] = {
        int(ta["turn"]): ta for ta in data.get("turn_assertions") or []
    }
    global_assertions = data.get("assertions") or {}

    customer_turn = 0
    all_failures: list[str] = []

    owned_pool = False
    effective_pool = None
    if with_db:
        if pool is not None:
            effective_pool = pool
        else:
            from sdr.config import get_settings
            from sdr.db import init_pool

            effective_pool = await init_pool(get_settings())
            owned_pool = True

    try:
        for turn in turns:
            if turn.get("role") != "customer":
                continue
            if turn.get("command") == "reset_memory":
                state = ConversationCanonicalState(
                    thread_id=state.thread_id,
                    customer=state.customer,
                )
                continue

            customer_turn += 1
            coalesce = turn.get("coalesce")
            if isinstance(coalesce, list) and coalesce:
                text = "\n".join(str(p.get("text") or "") for p in coalesce)
            else:
                text = str(turn.get("text") or "")

            before = state
            inbound = inbound_from_fixture_turn(turn, text, state.thread_id)

            try:
                if inbound is not None:
                    result = await process_turn(
                        state=state,
                        inbound=inbound,
                        understand=understand,
                        pool=effective_pool,
                    )
                else:
                    result = await process_turn(
                        state=state,
                        inbound_text=text,
                        understand=understand,
                        pool=effective_pool,
                    )
            except Exception as exc:
                all_failures.append(
                    f"turn {customer_turn}: process_turn raised {type(exc).__name__}: {exc}"
                )
                break

            if result.outbound_texts:
                result.state.assistant_turn_count = state.assistant_turn_count + 1
            state = result.state

            ta = turn_assertions.get(customer_turn)
            if ta:
                failures = _check_turn_assertions(customer_turn, ta, result, before)
                all_failures.extend(failures)
    finally:
        if owned_pool:
            from sdr.db import close_pool

            await close_pool()

    if global_assertions.get("no_reintro_after_first_turn"):
        pass

    if all_failures:
        print("\n".join(all_failures))
    return len(all_failures) == 0


def _resolve_fixture(name_or_path: str) -> str:
    from pathlib import Path

    given = Path(name_or_path)
    if given.exists():
        return str(given)
    fixtures_dir = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
    candidates = [
        fixtures_dir / f"{name_or_path}.yaml",
        fixtures_dir / f"{name_or_path}.yml",
        Path(f"{name_or_path}.yaml"),
        Path(f"{name_or_path}.yml"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(
        f"Fixture not found: {name_or_path!r}\nSearched: {[str(c) for c in candidates]}"
    )

