"""Polling worker — PENDING messages → orchestrator."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

import asyncpg
import redis.asyncio as redis

from sdr.config import Settings, get_settings
from sdr.db import init_pool
from sdr.infrastructure.conversation_repository import ConversationRepository
from sdr.infrastructure.evolution_client import EvolutionClient
from sdr.orchestrator import Orchestrator, StubEvolutionSender, default_understand
from sdr.redis_client import init_redis

logger = logging.getLogger(__name__)

UnderstandFn = Callable[..., Awaitable]


class LiveEvolutionSender:
    """Adapter: Orchestrator Protocol → EvolutionClient.send_text."""

    def __init__(self, client: EvolutionClient) -> None:
        self._client = client

    async def send_text(self, phone: str, text: str, *, instance: str) -> str | None:
        # Instance comes from Conversation row; EvolutionClient uses EVOLUTION_SDR_INSTANCE.
        _ = instance
        return await self._client.send_text(phone, text)


def _default_evolution(settings: Settings):
    if (settings.evolution_api_key or "").strip():
        return LiveEvolutionSender(EvolutionClient(settings))
    logger.warning("EVOLUTION_API_KEY empty — outbound WhatsApp uses StubEvolutionSender")
    return StubEvolutionSender()


async def process_pending_once(
    *,
    pool: asyncpg.Pool,
    redis_client: redis.Redis | None,
    settings: Settings | None = None,
    understand=default_understand,
    evolution=None,
    batch_size: int = 20,
) -> int:
    """Process up to ``batch_size`` PENDING inbound messages. Returns count handled."""
    cfg = settings or get_settings()
    conversations = ConversationRepository(pool)
    orch = Orchestrator(
        pool,
        redis_client,
        settings=cfg,
        understand=understand,
        evolution=evolution or _default_evolution(cfg),
    )

    rows = await conversations.list_batch_work_seeds(limit=batch_size)
    handled = 0
    for row in rows:
        try:
            await orch.process_batch_seed(row)
            handled += 1
        except RuntimeError as exc:
            # Lock contention is retryable next poll — not a poison message.
            if "Could not acquire lock" in str(exc):
                logger.warning("lock busy seed id=%s: %s", row["id"], exc)
                continue
            logger.exception("Failed processing batch seed id=%s", row["id"])
            handled += 1
        except Exception:
            logger.exception("Failed processing batch seed id=%s", row["id"])
            handled += 1
    return handled


async def run_worker_loop(
    *,
    poll_interval_s: float = 1.0,
    settings: Settings | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Long-running poll loop (CLI entry)."""
    cfg = settings or get_settings()
    pool = await init_pool(cfg)
    r = await init_redis(cfg)
    evolution = _default_evolution(cfg)
    stop = stop_event or asyncio.Event()
    logger.info(
        "SDR worker started julia_enabled=%s debounce_ms=%s evolution=%s instance=%s",
        cfg.julia_enabled,
        cfg.sdr_debounce_ms,
        type(evolution).__name__,
        cfg.evolution_sdr_instance,
    )
    while not stop.is_set():
        try:
            n = await process_pending_once(
                pool=pool,
                redis_client=r,
                settings=cfg,
                evolution=evolution,
            )
            if n:
                logger.info("Processed %s pending message(s)", n)
        except Exception:
            logger.exception("Worker loop error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=poll_interval_s)
        except asyncio.TimeoutError:
            pass


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker_loop())


if __name__ == "__main__":
    main()
