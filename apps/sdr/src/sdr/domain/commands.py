"""Protocol-deterministic inbound commands (not semantic heuristics).

Explicit slash commands are safe fast-paths: the customer intentionally
invokes an operational action. Do not extend this with free-text matching.
"""

from __future__ import annotations

import re

# Exact command after trim + casefold. No partial / natural-language matching.
_RESET_MEMORY_COMMAND = "/deletar"
_WHITESPACE = re.compile(r"\s+")


def normalize_command_text(text: str | None) -> str:
    if text is None:
        return ""
    return _WHITESPACE.sub(" ", str(text).strip()).casefold()


def is_reset_memory_command(text: str | None) -> bool:
    """True only when the inbound text is exactly ``/deletar`` (case-insensitive)."""
    return normalize_command_text(text) == _RESET_MEMORY_COMMAND


RESET_MEMORY_CONFIRMATION_PT = (
    "Pronto — limpei o contexto desta conversa. "
    "Pode começar o teste do zero quando quiser."
)
