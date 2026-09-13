"""Re-export of the Phase 11 follow-up double.

Frente A/B may replace this module with domain+scheduler adapters.
Replay runner imports ``sdr.replay.followup_harness`` directly.
"""

from sdr.replay.followup_harness import (  # noqa: F401
    FollowUpHarness,
    FollowUpTask,
    apply_clock_jump,
    two_workers_claim_once,
)
