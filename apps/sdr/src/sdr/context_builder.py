"""ConversationContextBuilder — single responsibility for context assembly.

All context needed by the Understanding Engine and Response Composer is built
here, in one place. No other module should construct LLM context independently.

Current scope (MVP):
- canonical state summary for the Understanding Engine
- composition payload for the Response Composer (ResponseDirective inputs)

Out of scope (not yet implemented):
- accumulated conversation summary (multi-turn summarization across sessions)
- bounded recent turn history from DB

When accumulated_summary is None, the builder still produces a valid context
using canonical state. This limited scope is documented as a known limitation.
"""

from __future__ import annotations

from typing import Any

from sdr.domain.facts_schema import CANONICAL_FACT_KEYS
from sdr.domain.inbound import InboundTurn
from sdr.domain.introduction import intro_instruction, response_objective_for
from sdr.domain.types import ActionPlan, ConversationCanonicalState

# Identity / document identifiers — never sent to Understanding or Composer.
_SENSITIVE_FACT_KEYS = frozenset({
    "cpf",
    "cnpj",
    "birth_date",
    "plate",
    "trade_renavam",
    "rg",
})

# Canonical customer facts plus CRM-linked titles. Derived from the schema so
# new trade/sale keys cannot silently drop out of the Understanding summary.
_SAFE_FACT_KEYS = CANONICAL_FACT_KEYS | {"crm_linked_vehicles"}


def _safe_facts(facts: dict[str, Any]) -> dict[str, Any]:
    """Return facts safe for LLM context — no operational metadata, no sensitive data."""
    return {
        k: v
        for k, v in facts.items()
        if k in _SAFE_FACT_KEYS
        and k not in _SENSITIVE_FACT_KEYS
        and v is not None
        and not str(k).startswith("_")
    }


class ConversationContextBuilder:
    """Builds structured context objects consumed by Understanding and Composer.

    Invariant: All context is derived from canonical state + explicit inputs.
    No module should build context independently.
    """

    def build_understanding_summary(
        self,
        state: ConversationCanonicalState,
        *,
        accumulated_summary: str | None = None,
        recent_turns: list[dict[str, Any]] | None = None,
        linked_vehicle_titles: list[str] | None = None,
    ) -> str:
        """Build a concise state summary for the Understanding Engine.

        The summary describes what is already known so the LLM extracts only
        new or corrected information, not redundant repeats.

        accumulated_summary: Optional multi-turn summary (not yet generated).
        recent_turns: Optional bounded list of recent turns (not yet fetched).
        When absent, state-based summary is used.
        """
        lines: list[str] = []

        if accumulated_summary:
            lines.append(f"Resumo da conversa: {accumulated_summary}")
        else:
            lines.append("(sem resumo acumulado — usando estado canônico)")

        lines.append(f"Intenção identificada: {state.intent.value}")
        lines.append(f"Idioma: {state.language}")
        lines.append(f"Status do lifecycle: {state.lifecycle.status.value}")
        lines.append(f"Turnos da Júlia nesta conversa: {state.assistant_turn_count}")
        lines.append(f"pending_interaction: {state.pending_interaction.value}")
        lines.append(f"alternative_scope: {state.alternative_scope.value}")
        lines.append(f"budget_status: {state.budget_status.value}")

        if state.customer.name:
            lines.append(f"Nome do cliente: {state.customer.name}")

        safe = _safe_facts(state.facts)
        if safe:
            lines.append("Dados já coletados:")
            for k, v in safe.items():
                lines.append(f"  {k}: {v}")

        if linked_vehicle_titles:
            titles = [t.strip() for t in linked_vehicle_titles if t and str(t).strip()]
            if titles:
                lines.append(
                    "Veículos já vinculados a este negócio (não perguntar de novo se o cliente só confirmar): "
                    + ", ".join(titles)
                )

        if state.pending_confirmation:
            lines.append(f"Aguardando confirmação de: {', '.join(state.pending_confirmation)}")

        if state.pending_interaction.value == "OFFER_ALTERNATIVES":
            lines.append(
                "Oferta pendente: o cliente deve aceitar/recusar alternativas. "
                "Preencha pending_resolution (ACCEPT|REJECT|AMBIGUOUS)."
            )

        if state.pending_question:
            lines.append(
                f"Última pergunta feita pela Júlia: '{state.pending_question}'. "
                "Se a resposta do cliente for 'sim', 'não', 'exato', 'isso', 'pode', 'claro' "
                "ou similar, interprete-a como confirmação/negação desta pergunta e preencha "
                "o campo correspondente nos facts."
            )

        if state.last_shown_vehicle_ids:
            lines.append(
                "ATENÇÃO — veículos já exibidos: o cliente já viu opções de estoque neste "
                "atendimento. Se a mensagem atual for um COMENTÁRIO ou PERGUNTA sobre o "
                "veículo exibido (cor, acabamento, motor, preço, elogio, curiosidade), "
                "NÃO preencha desired_vehicle_text, desired_model, nem engine_displacement_liters "
                "— esses campos já estão no estado canônico. Preencha desired_vehicle_text ou "
                "desired_model SOMENTE se o cliente expressar claramente preferência por um "
                "modelo diferente do que foi mostrado."
            )

        if recent_turns:
            lines.append("Mensagens recentes:")
            for t in recent_turns[-3:]:
                role = t.get("role", "?")
                text = str(t.get("text", ""))[:120]
                lines.append(f"  [{role}] {text}")

        return "\n".join(lines)

    def build_composition_payload(
        self,
        *,
        inbound: InboundTurn,
        state: ConversationCanonicalState,
        plan: ActionPlan,
        tool_results: list[dict[str, Any]],
        accumulated_summary: str | None = None,
    ) -> dict[str, Any]:
        """Build the payload passed to the Response Composer.

        This replaces scattered state_map/plan_map dictionaries built in
        process_turn and compose_response. One payload, one builder.
        """
        should_introduce = state.assistant_turn_count == 0
        objective = response_objective_for(
            action=plan.action, should_introduce=should_introduce
        )
        inbound_text = inbound.effective_text

        payload: dict[str, Any] = {
            "context": {
                "intent": state.intent.value,
                "language": state.language,
                "customer_name": state.customer.name,
                "facts": _safe_facts(state.facts),
                "lifecycle_status": state.lifecycle.status.value,
                "should_introduce": should_introduce,
                "intro_instruction": intro_instruction(should_introduce),
                "response_objective": objective,
                "inbound_text": inbound_text,
                "pending_confirmation": state.pending_confirmation,
                "claims_forbidden": [
                    "aprovação garantida",
                    "taxa fixa",
                    "parcela fixa",
                    "100% financiado",
                    "sem entrada garantido",
                    "financiamos 100%",
                    "consegue financiar 100%",
                    "financiar todo o valor",
                ],
            },
            "action_plan": {
                "action": plan.action.value,
                "ask_field": plan.ask_field,
                "next_question": plan.next_question,
                "reason_code": plan.reason_code,
                "handoff": plan.handoff,
            },
            "tool_results": tool_results,
            "inbound": {
                "content_type": inbound.content_type.value,
                "media_status": inbound.media_status.value,
                "failure_code": inbound.failure_code.value if inbound.failure_code else None,
                "text": inbound_text,
            },
        }

        if accumulated_summary:
            payload["accumulated_summary"] = accumulated_summary

        return payload
