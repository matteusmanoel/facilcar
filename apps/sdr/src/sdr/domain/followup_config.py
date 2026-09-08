"""Central follow-up intervals — no magic numbers in policy code.

All windows are commercial-clock relative (America/Sao_Paulo). The LLM
must not invent cadence, attempt counts, or silence delays.
"""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

TZ_NAME = "America/Sao_Paulo"
TZ = ZoneInfo(TZ_NAME)

# One automatic resume. A second attempt requires a new customer commitment.
MAX_ATTEMPTS = 1

# Do not schedule an instant in the immediate past / too close to now.
MIN_LEAD_TIME = timedelta(minutes=15)

# Silence after an unanswered actionable question before a NO_RESPONSE follow-up.
COMMERCIAL_SILENCE_WINDOW = timedelta(hours=4)

# After the single follow-up is sent, wait this long then move to DORMANT.
AWAITING_AFTER_FOLLOWUP_WINDOW = timedelta(hours=24)

# Day-only commitments ("amanhã") use this hour when the day is open.
DEFAULT_DAY_HOUR = 10
DEFAULT_DAY_MINUTE = 0
