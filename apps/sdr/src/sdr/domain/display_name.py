"""Customer-facing display names — never shout the CNH legal name."""

from __future__ import annotations

from sdr.domain.vendor_summary import is_placeholder_display_name


def display_first_name(name: str | None) -> str | None:
    """First token in title case. ``MATEUS MANOEL FERREIRA`` → ``Mateus``."""
    if not name or is_placeholder_display_name(name):
        return None
    token = name.strip().split()[0]
    if not token or "@" in token:
        return None
    return token[:1].upper() + token[1:].lower()
