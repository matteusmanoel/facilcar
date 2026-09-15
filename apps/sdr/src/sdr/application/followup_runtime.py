"""Production follow-up runtime — policy, persist, tick, compose.

Replay goldens and the worker share this path. The in-memory
``followup_harness`` double is unit-test only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import asyncio

from sdr.application.followup_scheduler import FollowUpScheduler, FollowUpSnapshot
from sdr.config import get_settings
from sdr.domain.conversation_revision import context_revision_is_usable
from sdr.domain.clock import TZ_BRT, now_brt
from sdr.domain.followup import (
    ConsentSource,
    EXPLICIT_TIME_ACK_PT,
    FollowUpDecision,
    FollowUpWaitState,
    PERMISSION_ASK_PT,
    PauseReason,
    apply_followup_transition,
    enrich_turn_facts_from_inbound,
    followup_decision,
    followup_record,
    followup_record_to_dict,
    mark_followup_sent,
    resume_after_customer_reply,
)
from sdr.domain.followup_cancel import FollowUpCancelReason, is_opt_out_signal
from sdr.domain.followup_plan import FollowUpAction, FollowUpPlan, FollowUpReason
from sdr.domain.document_commitment import (
    COMMITMENT_CLAIM_NONE,
    COMMITMENT_CLAIM_PROMISED,
    COMMITMENT_CLAIM_UNAVAILABLE,
)
from sdr.domain.types import ConversationCanonicalState, InventoryOutcome, LifecycleStatus, TurnFacts
from sdr.infrastructure.followup_repository import (
    ACTIVE_STATUSES,
    InMemoryFollowUpRepository,
    STATUS_CLAIMED,
    STATUS_PROCESSING,
)
from sdr.understanding.followup_composer import compose_followup

EXECUTION_MODE_PRODUCTION = "production_policy"
EXECUTION_MODE_DOUBLE = "followup_harness_double"

_PAUSE_TO_PLAN = {
    PauseReason.DOCUMENTS_UNAVAILABLE: (FollowUpReason.DOCUMENTS_PENDING, FollowUpAction.ASK_DOCUMENTS_STATUS),
    PauseReason.DOCUMENTS_PROMISED: (FollowUpReason.DOCUMENTS_PENDING, FollowUpAction.ASK_DOCUMENTS_STATUS),
    PauseReason.DECISION_WITH_PARTNER: (FollowUpReason.PARTNER_DECISION, FollowUpAction.ASK_PARTNER_DECISION),
    PauseReason.THINKING: (FollowUpReason.PARTNER_DECISION, FollowUpAction.ASK_PARTNER_DECISION),
    PauseReason.CUSTOMER_WILL_RETURN: (FollowUpReason.SPECIFIC_VEHICLE, FollowUpAction.ASK_VEHICLE_INTEREST),
    PauseReason.NO_RESPONSE_AFTER_QUESTION: (FollowUpReason.SPECIFIC_VEHICLE, FollowUpAction.ASK_VEHICLE_INTEREST),
    PauseReason.VISIT_FUTURE_CONTACT: (FollowUpReason.SPECIFIC_VEHICLE, FollowUpAction.ASK_VEHICLE_INTEREST),
    PauseReason.OTHER_CONTEXTUAL_PAUSE: (FollowUpReason.CATEGORY_INTEREST, FollowUpAction.ASK_CATEGORY_INTEREST),
}


def _plan_reason(pause: PauseReason | None) -> tuple[str, str]:
    if pause is None:
        return FollowUpReason.SPECIFIC_VEHICLE.value, FollowUpAction.ASK_VEHICLE_INTEREST.value
    mapped = _PAUSE_TO_PLAN.get(pause)
    if mapped is None:
        return FollowUpReason.SPECIFIC_VEHICLE.value, FollowUpAction.ASK_VEHICLE_INTEREST.value
    return mapped[0].value, mapped[1].value


@dataclass
class FollowUpEvidence:
    policy_called: bool = False
    eligibility_evaluated: bool = False
    schedule_computed: bool = False
    task_persisted: bool = False
    scheduler_claimed: bool = False
    pre_send_checks_executed: bool = False
    composer_called: bool = False
    execution_mode: str = EXECUTION_MODE_PRODUCTION
    context_revision_loaded: bool = False
    context_revision_nonzero: bool = False
    context_revision_checked_before_compose: bool = False
    context_revision_checked_before_send: bool = False
    context_revision: int | None = None
    ownership_revision: int | None = None
    consent_source: str | None = None
    customer_agreed_at: str | None = None
    fallback_resume_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy_called": self.policy_called,
            "eligibility_evaluated": self.eligibility_evaluated,
            "schedule_computed": self.schedule_computed,
            "task_persisted": self.task_persisted,
            "scheduler_claimed": self.scheduler_claimed,
            "pre_send_checks_executed": self.pre_send_checks_executed,
            "composer_called": self.composer_called,
            "execution_mode": self.execution_mode,
            "context_revision_loaded": self.context_revision_loaded,
            "context_revision_nonzero": self.context_revision_nonzero,
            "context_revision_checked_before_compose": self.context_revision_checked_before_compose,
            "context_revision_checked_before_send": self.context_revision_checked_before_send,
            "context_revision": self.context_revision,
            "ownership_revision": self.ownership_revision,
            "consent_source": self.consent_source,
            "customer_agreed_at": self.customer_agreed_at,
            "fallback_resume_at": self.fallback_resume_at,
        }


@dataclass
class FollowUpRuntime:
    conversation_id: str
    repo: InMemoryFollowUpRepository = field(default_factory=InMemoryFollowUpRepository)
    opted_out_at: datetime | None = None
    evidence: FollowUpEvidence = field(default_factory=FollowUpEvidence)
    last_decision: FollowUpDecision | None = None
    last_state: ConversationCanonicalState | None = None
    inventory: dict[str, str] = field(default_factory=dict)
    ownership_revision: int = 0
    context_revision: int = 0
    bot_status: str = LifecycleStatus.BOT_ACTIVE.value
    last_inbound_at: datetime | None = None
    phone: str = ""
    sends: list[str] = field(default_factory=list)
    composer_calls: int = 0
    llm_calls: int = 0
    clock_jumps: list[dict[str, Any]] = field(default_factory=list)
    last_tick_sent: list[str] = field(default_factory=list)
    last_tick_rescheduled: list[dict[str, Any]] = field(default_factory=list)
    last_tick_cancelled: list[str] = field(default_factory=list)
    last_tick_claims: list[dict[str, Any]] = field(default_factory=list)
    cancels: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    transitions: list[dict[str, Any]] = field(default_factory=list)

    def record_clock_jump(self, jump: Any, instant: datetime) -> None:
        self.clock_jumps.append({"jump": jump, "clock": instant.isoformat()})

    def override_inventory(self, override: dict[str, Any]) -> dict[str, Any]:
        vid = str(override.get("vehicle_id") or override.get("id") or "")
        status = str(override.get("status") or "")
        if vid:
            self.inventory[vid] = status
        return {"vehicle_id": vid, "status": status}

    def has_pending(self) -> bool:
        return any(
            t.status in ACTIVE_STATUSES and t.sent_at is None for t in self.repo.all_rows()
        )

    async def cancel(self, reason: str) -> list[Any]:
        rows = await self.repo.cancel_pending_for_conversation(self.conversation_id, reason)
        for task in rows:
            self.cancels.append(
                {
                    "id": task.id,
                    "cancelReason": task.cancel_reason,
                    "status": task.status,
                }
            )
        return rows

    async def on_reset(self) -> None:
        await self.cancel(FollowUpCancelReason.CONVERSATION_RESET.value)

    def on_admin(self, event_name: str, state: ConversationCanonicalState | None = None) -> None:
        current = state if state is not None else self.last_state
        if event_name in {"assume", "ADMIN_ASSUME"}:
            self.bot_status = LifecycleStatus.HUMAN_ACTIVE.value
            if current is not None:
                self.ownership_revision = int(getattr(current, "ownership_revision", 0) or 0)
            else:
                self.ownership_revision = int(self.ownership_revision or 0) + 1
        if current is not None:
            self.last_state = current

    def _iso(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_BRT)
        else:
            dt = dt.astimezone(TZ_BRT)
        return dt.isoformat()

    def task_dicts(self) -> list[dict[str, Any]]:
        return [
            {
                "id": t.id,
                "conversationId": t.conversation_id,
                "reason": t.reason,
                "status": t.status,
                "scheduledAt": self._iso(t.scheduled_at),
                "originalTemporalText": t.original_temporal_text,
                "consentSource": t.consent_source,
                "consentLevel": t.consent_level,
                "attemptNumber": t.attempt_number,
                "idempotencyKey": t.idempotency_key,
                "sentAt": self._iso(t.sent_at),
                "cancelledAt": self._iso(t.cancelled_at),
                "cancelReason": t.cancel_reason,
                "contextRevision": t.context_revision,
                "ownershipRevision": t.ownership_revision,
            }
            for t in self.repo.all_rows()
        ]

    def persist_opt_out(self, state: ConversationCanonicalState | None = None) -> None:
        self.opted_out_at = self.opted_out_at or now_brt()
        if state is not None:
            state.sdr_opted_out_at = self.opted_out_at.isoformat()
            record = followup_record(state)
            record.opted_out = True
            record.pause_reason = PauseReason.OPT_OUT

    def is_opted_out(self) -> bool:
        return self.opted_out_at is not None

    def stamp_opt_out_on_state(self, state: ConversationCanonicalState) -> None:
        if not self.is_opted_out():
            return
        self.persist_opt_out(state)

    def apply_policy(
        self,
        state: ConversationCanonicalState,
        inbound_text: str,
        facts: TurnFacts | None = None,
    ) -> FollowUpDecision:
        facts = facts or TurnFacts()
        enrich_turn_facts_from_inbound(facts, inbound_text)
        if self.is_opted_out() or is_opt_out_signal(inbound_text, facts):
            self.persist_opt_out(state)
            facts.pause_reason = PauseReason.OPT_OUT.value
        self.evidence.policy_called = True
        decision = followup_decision(state, facts, inbound_text=inbound_text)
        self.evidence.eligibility_evaluated = True
        if decision.schedule_at is not None or decision.fallback_resume_at is not None:
            self.evidence.schedule_computed = True
        apply_followup_transition(state, decision)
        self.last_decision = decision
        self.last_state = state
        self.phone = str(getattr(state.customer, "phone", "") or "")
        self.ownership_revision = int(getattr(state, "ownership_revision", 0) or 0)
        self.context_revision = int(getattr(state, "context_revision", 0) or 0)
        self.bot_status = state.lifecycle.status.value
        record = followup_record(state)
        self.evidence.consent_source = record.consent_source
        self.evidence.fallback_resume_at = record.fallback_resume_at
        self.evidence.customer_agreed_at = (
            record.scheduled_at
            if record.consent_source == ConsentSource.EXPLICIT_CUSTOMER_TIME.value
            else None
        )
        return decision

    async def sync_task(
        self,
        state: ConversationCanonicalState,
        inbound_text: str,
        *,
        cancel_reason: str | None = None,
    ) -> None:
        if cancel_reason:
            await self.cancel(cancel_reason)
            return
        if self.is_opted_out():
            await self.cancel(FollowUpCancelReason.OPT_OUT.value)
            return
        decision = self.last_decision
        if decision is None:
            return
        when = decision.schedule_at or (
            decision.fallback_resume_at
            if decision.consent_source
            in {
                ConsentSource.CONTEXTUAL_SINGLE_ATTEMPT,
                ConsentSource.EXPLICIT_PERMISSION,
            }
            else None
        )
        if when is None or not decision.eligible:
            return
        if decision.consent_source in {
            ConsentSource.CONTEXTUAL_SINGLE_ATTEMPT,
            ConsentSource.EXPLICIT_PERMISSION,
        }:
            original = decision.original_temporal_text or inbound_text
        else:
            original = decision.original_temporal_text
        key = f"{self.conversation_id}:{when.isoformat()}:{decision.pause_reason}"
        captured = int(getattr(state, "context_revision", 0) or 0)
        if not context_revision_is_usable(captured):
            return
        await self.repo.create_or_supersede(
            conversation_id=self.conversation_id,
            reason=(decision.pause_reason.value if decision.pause_reason else "OTHER_CONTEXTUAL_PAUSE"),
            scheduled_at=when,
            idempotency_key=key,
            original_temporal_text=original,
            consent_source=decision.consent_source.value,
            consent_level=decision.consent_level.value,
            context_revision=captured,
            ownership_revision=int(getattr(state, "ownership_revision", 0) or 0),
            maximum_attempts=decision.maximum_attempts,
            now=now_brt(),
        )
        self.evidence.task_persisted = True
        self.evidence.context_revision_loaded = True
        self.evidence.context_revision_nonzero = True
        self.evidence.context_revision = captured
        self.evidence.ownership_revision = int(getattr(state, "ownership_revision", 0) or 0)
        self.context_revision = captured
        self.last_state = state

    def snapshot(self) -> FollowUpSnapshot:
        loaded = context_revision_is_usable(self.context_revision)
        phone = self.phone
        if not phone and self.last_state is not None:
            phone = str(getattr(self.last_state.customer, "phone", "") or "")
        return FollowUpSnapshot(
            conversation_id=self.conversation_id,
            bot_status=self.bot_status,
            ownership_revision=self.ownership_revision,
            context_revision=self.context_revision if loaded else None,
            last_inbound_at=self.last_inbound_at,
            opt_out=self.is_opted_out(),
            closed=self.bot_status == LifecycleStatus.HUMAN_CLOSED.value,
            commercial_ok=not self.is_opted_out(),
            revision_loaded=loaded,
            phone=phone,
        )

    def replay_snapshot(self, state: ConversationCanonicalState | None = None) -> dict[str, Any]:
        current = state if state is not None else self.last_state
        rows = self.repo.all_rows()
        return {
            "wait_state": self.wait_state_of(current) if current is not None else FollowUpWaitState.ACTIVE_QUALIFICATION.value,
            "followup_sends": len(self.sends),
            "composer_calls": self.composer_calls,
            "task_count": len(rows),
            "pending": sum(1 for t in rows if t.status in ACTIVE_STATUSES),
            "cancelled": sum(1 for t in rows if t.status == "CANCELLED"),
            "idempotency_keys": [t.idempotency_key for t in rows],
            "inventory": dict(self.inventory),
            **self.evidence.as_dict(),
        }

    def _inventory_tools(self) -> list[dict[str, Any]]:
        if any(status == "SOLD" for status in self.inventory.values()):
            return [
                {
                    "tool": "inventory_search",
                    "outcome": InventoryOutcome.SUCCESS_SOLD.value,
                    "vehicles": [
                        {"status": "SOLD", "id": vid}
                        for vid, status in self.inventory.items()
                        if status == "SOLD"
                    ],
                }
            ]
        if self.inventory:
            return [
                {
                    "tool": "inventory_search",
                    "outcome": InventoryOutcome.SUCCESS_FOUND.value,
                    "vehicles": [
                        {"status": status, "id": vid}
                        for vid, status in self.inventory.items()
                    ],
                }
            ]
        return [
            {
                "tool": "inventory_search",
                "outcome": InventoryOutcome.NOT_EXECUTED.value,
                "vehicles": [],
            }
        ]

    async def compose_task(self, task, snapshot: FollowUpSnapshot) -> str:
        self.evidence.pre_send_checks_executed = True
        self.evidence.context_revision_checked_before_compose = True
        if not snapshot.revision_loaded or not context_revision_is_usable(
            snapshot.context_revision
        ):
            return ""
        if snapshot.context_revision != task.context_revision:
            return ""
        if snapshot.opt_out or snapshot.bot_status == LifecycleStatus.HUMAN_ACTIVE.value:
            return ""
        if str(task.status) not in {STATUS_PROCESSING, STATUS_CLAIMED}:
            return ""
        pause = None
        try:
            pause = PauseReason(task.reason)
        except ValueError:
            pause = None
        reason, action = _plan_reason(pause)
        pause_value = pause.value if pause is not None else ""
        authorized = pause_value == PauseReason.DOCUMENTS_PROMISED.value
        if authorized:
            claim = COMMITMENT_CLAIM_PROMISED
        elif pause_value == PauseReason.DOCUMENTS_UNAVAILABLE.value:
            claim = COMMITMENT_CLAIM_UNAVAILABLE
        else:
            claim = COMMITMENT_CLAIM_NONE
        plan = FollowUpPlan(
            reason=reason,
            requested_action=action,
            vehicle_label=None,
            pending_commitment=task.original_temporal_text,
            authorized_commitment=authorized,
            commitment_claim=claim,
            authorized_facts={
                "pending_commitment": task.original_temporal_text,
                "authorized_commitment": authorized,
                "commitment_claim": claim,
            },
        )
        self.composer_calls += 1
        self.evidence.composer_called = True
        result = await compose_followup(plan, tool_results=self._inventory_tools())
        if result.strategy == "cancel_safe":
            cancelled = await self.repo.cancel(
                task.id, FollowUpCancelReason.VEHICLE_NO_LONGER_APPLICABLE.value
            )
            if cancelled is not None:
                self.cancels.append(
                    {
                        "id": cancelled.id,
                        "cancelReason": cancelled.cancel_reason,
                        "status": cancelled.status,
                    }
                )
            if self.last_state is not None:
                apply_followup_transition(
                    self.last_state,
                    FollowUpDecision(
                        eligible=False,
                        wait_state=FollowUpWaitState.DORMANT,
                        reason_code="vehicle_no_longer_applicable",
                    ),
                )
            return ""
        if not result.sendable or not result.bubbles:
            return ""
        return result.bubbles[0]

    async def _load_snapshot(self, _conversation_id: str) -> FollowUpSnapshot:
        return self.snapshot()

    async def send_task(self, task, text: str) -> None:
        self.sends.append(text)

    async def tick(self, *, workers: list[str] | None = None) -> list[Any]:
        workers = workers or ["w1"]
        before = len(self.sends)
        schedulers = [
            FollowUpScheduler(
                self.repo,
                worker_id=worker,
                now_brt=now_brt,
                composer=self.compose_task,
                sender=self.send_task,
                load_snapshot=self._load_snapshot,
                settings=get_settings(),
            )
            for worker in workers
        ]
        batches = await asyncio.gather(*[scheduler.tick() for scheduler in schedulers])
        results = [item for batch in batches for item in batch]
        self.evidence.scheduler_claimed = True
        self.evidence.pre_send_checks_executed = True
        self.evidence.context_revision_checked_before_compose = (
            self.evidence.context_revision_checked_before_compose
            or any(s.context_checked_before_compose for s in schedulers)
        )
        self.evidence.context_revision_checked_before_send = (
            self.evidence.context_revision_checked_before_send
            or any(s.context_checked_before_send for s in schedulers)
        )
        if context_revision_is_usable(self.context_revision):
            self.evidence.context_revision_loaded = True
            self.evidence.context_revision_nonzero = True
            self.evidence.context_revision = self.context_revision
        self.evidence.ownership_revision = self.ownership_revision
        self.last_tick_sent = self.sends[before:]
        self.last_tick_rescheduled = [
            {"task_id": r.task_id, "action": r.action}
            for r in results
            if r.action == "rescheduled"
        ]
        self.last_tick_cancelled = [r.task_id for r in results if r.action == "cancelled"]
        self.last_tick_claims = [
            {"task_id": r.task_id, "action": r.action} for r in results if r.action == "sent"
        ]
        self.claims.extend(self.last_tick_claims)
        if self.last_tick_sent and self.last_state is not None:
            mark_followup_sent(self.last_state)
        return results

    def wait_state_of(self, state: ConversationCanonicalState | None) -> str:
        if state is None:
            return FollowUpWaitState.ACTIVE_QUALIFICATION.value
        return getattr(state, "wait_state", None) or FollowUpWaitState.ACTIVE_QUALIFICATION.value

    def policy_artifact(self, state: ConversationCanonicalState) -> dict[str, Any]:
        record = followup_record(state)
        decision = self.last_decision
        return {
            "execution_mode": EXECUTION_MODE_PRODUCTION,
            "wait_state": self.wait_state_of(state),
            "followup": followup_record_to_dict(record),
            "consent_source": record.consent_source,
            "permission_requested": record.permission_requested,
            "fallback_resume_at": record.fallback_resume_at,
            "agreed_by_customer": record.consent_source
            == ConsentSource.EXPLICIT_CUSTOMER_TIME.value,
            "customer_agreed_at": record.scheduled_at
            if record.consent_source == ConsentSource.EXPLICIT_CUSTOMER_TIME.value
            else None,
            "opted_out_at": self.opted_out_at.isoformat() if self.opted_out_at else None,
            "decision_reason_code": decision.reason_code if decision else None,
            **self.evidence.as_dict(),
        }


def immediate_pause_bubbles(decision: FollowUpDecision) -> list[str]:
    if decision.cancel_intent is not None:
        return []
    if decision.permission_requested:
        return [PERMISSION_ASK_PT]
    if decision.consent_source == ConsentSource.EXPLICIT_CUSTOMER_TIME:
        return [EXPLICIT_TIME_ACK_PT]
    return []
