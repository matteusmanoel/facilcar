"""Unit tests for phone / JID normalization."""

from __future__ import annotations

from sdr.domain.phone import normalize_phone, phone_from_jid


def test_normalize_digits_only() -> None:
    assert normalize_phone("(11) 99999-8888") == "11999998888"


def test_normalize_with_country_code() -> None:
    assert normalize_phone("+55 11 98888-7777") == "5511988887777"


def test_normalize_jid() -> None:
    assert normalize_phone("5511999999999@s.whatsapp.net") == "5511999999999"
    assert phone_from_jid("5511888777666@s.whatsapp.net") == "5511888777666"


def test_normalize_jid_strips_device_suffix() -> None:
    assert normalize_phone("5511999000101:12@s.whatsapp.net") == "5511999000101"


def test_normalize_empty() -> None:
    assert normalize_phone(None) == ""
    assert normalize_phone("") == ""
    assert normalize_phone("   ") == ""
