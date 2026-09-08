"""Reserved provider ids for bot outbound intent (Phase 11 Frente F).

Evolution assigns the real ``providerMessageId`` only after ``send_*``.
Persisting ``isBotSent`` first, under ``bot-pending-{uuid}``, lets a later
echo correlate instead of looking like unmatched human fromMe.

The Evolution HTTP API cannot close the remaining window where an echo
arrives with a real id whose text does not match the reserved bubble.
"""

from __future__ import annotations

import uuid

RESERVED_BOT_PROVIDER_PREFIX = "bot-pending-"
RESERVED_BOT_PROVIDER_LIKE = f"{RESERVED_BOT_PROVIDER_PREFIX}%"


def new_reserved_bot_provider_id() -> str:
    return f"{RESERVED_BOT_PROVIDER_PREFIX}{uuid.uuid4()}"


def is_reserved_bot_provider_id(provider_message_id: str | None) -> bool:
    pid = (provider_message_id or "").strip()
    return pid.startswith(RESERVED_BOT_PROVIDER_PREFIX)
