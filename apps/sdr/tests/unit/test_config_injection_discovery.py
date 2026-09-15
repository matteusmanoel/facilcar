"""Phase 13A-R1 — Vitest does not hide real SDR defaults."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def test_conftest_does_not_exclude_or_hide_discovery() -> None:
    text = (REPO / "apps/sdr/tests/conftest.py").read_text(encoding="utf-8")
    assert "collect_ignore" not in text
    assert "pytest_ignore_collect" not in text
    assert "norecursedirs" not in text
    assert "setdefault" in text


def test_vitest_config_does_not_exclude_sdr_tests() -> None:
    text = (REPO / "apps/web/vitest.config.ts").read_text(encoding="utf-8")
    assert "exclude" not in text.split("test:")[1].split("resolve:")[0]
    assert "features/**/*.test.ts" in text
    assert "features/**/__tests__/**/*.ts" in text
