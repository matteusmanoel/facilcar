"""Phase 13A-R1 — Compose healthcheck is config-readiness, not mere liveness."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def test_prod_compose_healthcheck_uses_ready_config() -> None:
    text = (REPO / "docker-compose.sdr.prod.yml").read_text(encoding="utf-8")
    api_block = text.split("facilcar-sdr-api:")[1].split("facilcar-sdr-worker:")[0]
    assert "/ready/config" in api_block
    assert "127.0.0.1:8000/health')" not in api_block.replace(" ", "")
    assert "/health" not in api_block.split("healthcheck:")[1]
    assert "postgres" not in api_block.split("healthcheck:")[1].lower()
    assert "evolution" not in api_block.split("healthcheck:")[1].lower()
