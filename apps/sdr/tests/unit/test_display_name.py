"""Customer-facing first name is title-case, never CNH shout-case."""

from __future__ import annotations

from sdr.domain.display_name import display_first_name


def test_cnh_all_caps_becomes_title_first_token() -> None:
    assert display_first_name("MATEUS MANOEL FERREIRA") == "Mateus"


def test_placeholder_is_omitted() -> None:
    assert display_first_name("WhatsApp 0845") is None
    assert display_first_name(None) is None
