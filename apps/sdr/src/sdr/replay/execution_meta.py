"""Per-scenario execution metadata — never one global label that contradicts the path.

policy_mode: production_policy | followup_harness_double
scheduler_mode: controlled_tick | double | hosted
llm_mode: live | stub
persistence_mode: isolated | database
scheduler_hosted: production process ticking Postgres (out of Phase 12 scope)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

POLICY_PRODUCTION = "production_policy"
POLICY_DOUBLE = "followup_harness_double"
SCHEDULER_CONTROLLED_TICK = "controlled_tick"
SCHEDULER_DOUBLE = "double"
SCHEDULER_HOSTED = "hosted"
LLM_LIVE = "live"
LLM_STUB = "stub"
PERSISTENCE_ISOLATED = "isolated"
PERSISTENCE_DATABASE = "database"


@dataclass(slots=True)
class ExecutionMeta:
    scenario_execution_mode: str
    policy_mode: str
    scheduler_mode: str
    llm_mode: str
    persistence_mode: str
    scheduler_hosted: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_execution_mode": self.scenario_execution_mode,
            "policy_mode": self.policy_mode,
            "scheduler_mode": self.scheduler_mode,
            "llm_mode": self.llm_mode,
            "persistence_mode": self.persistence_mode,
            "scheduler_hosted": self.scheduler_hosted,
        }


def replay_execution_meta(
    *,
    scenario_execution_mode: str,
    use_followup_double: bool,
    llm_real: bool,
) -> ExecutionMeta:
    if use_followup_double:
        policy = POLICY_DOUBLE
        scheduler = SCHEDULER_DOUBLE
    else:
        policy = POLICY_PRODUCTION
        scheduler = SCHEDULER_CONTROLLED_TICK
    return ExecutionMeta(
        scenario_execution_mode=scenario_execution_mode or policy,
        policy_mode=policy,
        scheduler_mode=scheduler,
        llm_mode=LLM_LIVE if llm_real else LLM_STUB,
        persistence_mode=PERSISTENCE_ISOLATED,
        scheduler_hosted=False,
    )


def phase12_regression_meta(*, llm_real: bool) -> ExecutionMeta:
    return ExecutionMeta(
        scenario_execution_mode=POLICY_PRODUCTION,
        policy_mode=POLICY_PRODUCTION,
        scheduler_mode=SCHEDULER_CONTROLLED_TICK,
        llm_mode=LLM_LIVE if llm_real else LLM_STUB,
        persistence_mode=PERSISTENCE_ISOLATED,
        scheduler_hosted=False,
    )
