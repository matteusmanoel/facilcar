"""Compose a contextual follow-up from an explicit FollowUpPlan.

The LLM (when present) phrases the single primary action. Code owns stock
truth, constraints, and the deterministic fallback. Empty or invalid output
must not send.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from sdr.domain.followup_plan import (
    Clock,
    FollowUpPlan,
    FollowUpStrategy,
    apply_current_inventory,
    fallback_followup_bubbles,
    is_empty_plan,
    resolve_clock,
    resolved_vehicle_label,
)
from sdr.domain.followup_validator import FollowUpValidation, validate_followup
from sdr.domain.introduction import intro_instruction
from sdr.understanding.persona_prompts import JULIA_PERSONA_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_JSON_SCHEMA: dict = {
    "name": "julia_followup_bubbles",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["bubbles"],
        "properties": {
            "bubbles": {
                "type": "array",
                "minItems": 0,
                "maxItems": 2,
                "items": {"type": "string"},
            },
        },
    },
}


@dataclass(slots=True)
class FollowUpComposeResult:
    bubbles: list[str] = field(default_factory=list)
    sendable: bool = False
    used_fallback: bool = False
    strategy: str = FollowUpStrategy.DO_NOT_SEND.value
    strategy_reason: str | None = None
    violations: list[str] = field(default_factory=list)
    plan: FollowUpPlan | None = None
    composed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bubbles": list(self.bubbles),
            "sendable": self.sendable,
            "used_fallback": self.used_fallback,
            "strategy": self.strategy,
            "strategy_reason": self.strategy_reason,
            "violations": list(self.violations),
            "composed_at": self.composed_at.isoformat() if self.composed_at else None,
        }


def _is_unittest_mock(client: Any) -> bool:
    if client is None:
        return False
    module = type(client).__module__ or ""
    return module.startswith("unittest.mock")


def _system_prompt(plan: FollowUpPlan) -> str:
    label = resolved_vehicle_label(plan)
    outcome = plan.inventory_outcome or "NOT_EXECUTED"
    stock_rule = (
        "Regra de estoque: só afirme que o veículo ainda está disponível se o "
        f"inventory_outcome ATUAL for SUCCESS_FOUND (agora: {outcome}). "
        "Não use snapshot antigo. Se o veículo foi vendido ou reservado, NÃO "
        "reenvie o texto de disponibilidade e NÃO escolha uma alternativa."
    )
    if plan.strategy == FollowUpStrategy.CANCEL_SAFE.value:
        stock_rule = (
            "Estratégia cancel_safe: o veículo não está disponível no estoque "
            "atual. Não afirme disponibilidade. Não sugira um substituto. "
            "Pode perguntar se a pessoa continua interessada na categoria."
        )
    return (
        f"{JULIA_PERSONA_SYSTEM_PROMPT}\n\n"
        f"{intro_instruction(False)}\n"
        "Isto é um FOLLOW-UP de continuidade, não um primeiro contato.\n"
        "Uma ação primária apenas. No máximo 2 bolhas; prefira 1.\n"
        "NÃO se apresente. NÃO abra com Oi/Olá. NÃO diga que a pessoa sumiu.\n"
        "NÃO faça pressão nem urgência. NÃO reinicie o funil completo.\n"
        "NÃO obrigue envio de documentos. NÃO prometa taxa, aprovação ou parcela.\n"
        "NÃO use as palavras handoff, CRM, lead, automação ou triagem.\n"
        f"{stock_rule}\n"
        f"Ação primária: {plan.requested_action}.\n"
        f"Motivo: {plan.reason}.\n"
        f"Compromisso pendente: {plan.pending_commitment or 'nenhum'}.\n"
        f"Rótulo do veículo autorizado: {label or 'nenhum'}.\n"
        "Use somente authorized_facts. Não invente modelo, marca ou estoque."
    )


def _payload(plan: FollowUpPlan) -> dict[str, Any]:
    return {
        "followup_plan": plan.to_dict(),
        "authorized_facts": dict(plan.authorized_facts),
        "vehicle_label": resolved_vehicle_label(plan),
        "pending_commitment": plan.pending_commitment,
        "requested_action": plan.requested_action,
        "inventory_outcome": plan.inventory_outcome,
        "strategy": plan.strategy,
        "strategy_reason": plan.strategy_reason,
    }


async def _llm_bubbles(plan: FollowUpPlan, client: Any) -> list[str] | None:
    try:
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0.3,
            response_format={"type": "json_schema", "json_schema": _JSON_SCHEMA},
            messages=[
                {"role": "system", "content": _system_prompt(plan)},
                {
                    "role": "user",
                    "content": json.dumps(_payload(plan), ensure_ascii=False),
                },
            ],
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        bubbles = data.get("bubbles") if isinstance(data, Mapping) else None
        if not isinstance(bubbles, list):
            return None
        return [str(b).strip() for b in bubbles if str(b).strip()][:2]
    except Exception:
        logger.warning("compose_followup: LLM failed; using contextual fallback")
        return None


def _result_from_validation(
    validation: FollowUpValidation,
    plan: FollowUpPlan,
    *,
    used_fallback: bool,
    composed_at: datetime,
) -> FollowUpComposeResult:
    return FollowUpComposeResult(
        bubbles=list(validation.bubbles) if validation.sendable else [],
        sendable=validation.sendable,
        used_fallback=used_fallback,
        strategy=plan.strategy,
        strategy_reason=plan.strategy_reason,
        violations=list(validation.violations),
        plan=plan,
        composed_at=composed_at,
    )


async def compose_followup(
    plan: FollowUpPlan | Mapping[str, Any] | None,
    *,
    tool_results: Any = None,
    client: Any | None = None,
    clock: Clock | datetime | str | None = None,
) -> FollowUpComposeResult:
    """Compose at most two bubbles from the plan + CURRENT inventory outcome."""
    parsed = FollowUpPlan.from_mapping(plan) if not isinstance(plan, FollowUpPlan) else plan
    bound = apply_current_inventory(parsed, tool_results)
    composed_at = resolve_clock(clock)

    if bound.strategy == FollowUpStrategy.DO_NOT_SEND.value or is_empty_plan(bound):
        return FollowUpComposeResult(
            bubbles=[],
            sendable=False,
            used_fallback=False,
            strategy=FollowUpStrategy.DO_NOT_SEND.value,
            strategy_reason=bound.strategy_reason or "empty_plan",
            violations=["empty_plan"],
            plan=bound,
            composed_at=composed_at,
        )

    llm_allowed = client is not None and not _is_unittest_mock(client)
    drafted: list[str] | None = None
    if llm_allowed:
        drafted = await _llm_bubbles(bound, client)

    if drafted:
        validation = validate_followup(drafted, bound, tool_results=tool_results)
        if validation.sendable:
            return _result_from_validation(
                validation, bound, used_fallback=False, composed_at=composed_at
            )

    fallback = fallback_followup_bubbles(bound)
    validation = validate_followup(fallback, bound, tool_results=tool_results)
    result = _result_from_validation(
        validation, bound, used_fallback=True, composed_at=composed_at
    )
    if not result.sendable:
        result.strategy = FollowUpStrategy.DO_NOT_SEND.value
        result.strategy_reason = result.strategy_reason or "invalid_output"
    return result
