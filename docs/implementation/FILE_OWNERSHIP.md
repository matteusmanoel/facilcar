# FILE_OWNERSHIP — Single-Writer Registry

> Each file/directory is owned by exactly one agent role.
> Concurrent writes to the same file by different agents are PROHIBITED.

## `apps/sdr/` (new Python service)

| Path | Owner | Wave |
|------|-------|------|
| `apps/sdr/pyproject.toml` | SDR CORE WORKER | 0 |
| `apps/sdr/Dockerfile` | SDR CORE WORKER | 0 |
| `apps/sdr/.env.example` | SDR CORE WORKER | 0 |
| `apps/sdr/src/sdr/main.py` | SDR CORE WORKER | 0 |
| `apps/sdr/src/sdr/config.py` | SDR CORE WORKER | 0 |
| `apps/sdr/src/sdr/db.py` | SDR CORE WORKER | 0 | connection layer only — schema via Prisma (ADR-003) |
| `apps/sdr/src/sdr/redis_client.py` | SDR CORE WORKER | 0 |
| `apps/sdr/src/sdr/api/health.py` | SDR CORE WORKER | 0 |
| `apps/sdr/src/sdr/api/webhook.py` | SDR CORE WORKER | 0 |
| `apps/sdr/src/sdr/domain/types.py` | SDR CORE WORKER | 1 |
| `apps/sdr/src/sdr/domain/merge.py` | SDR CORE WORKER | 1 |
| `apps/sdr/src/sdr/domain/qualifications.py` | SDR CORE WORKER | 1 |
| `apps/sdr/src/sdr/domain/decision.py` | SDR CORE WORKER | 1 |
| `apps/sdr/src/sdr/domain/handoff.py` | SDR CORE WORKER | 1/3 |
| `apps/sdr/src/sdr/orchestrator.py` | SDR CORE WORKER | 1 |
| `apps/sdr/src/sdr/worker.py` | SDR CORE WORKER | 1 |
| `apps/sdr/src/sdr/locks.py` | SDR CORE WORKER | 1 |
| `apps/sdr/src/sdr/debounce.py` | SDR CORE WORKER | 1 |
| `apps/sdr/src/sdr/understanding/extractor.py` | AI / LLM WORKER | 1 |
| `apps/sdr/src/sdr/understanding/prompts.py` | AI / LLM WORKER | 1 |
| `apps/sdr/src/sdr/understanding/response_composer.py` | AI / LLM WORKER | 1 |
| `apps/sdr/src/sdr/understanding/persona_prompts.py` | AI / LLM WORKER | 1 |
| `apps/sdr/src/sdr/infrastructure/lead_repository.py` | DATABASE WORKER | 1 |
| `apps/sdr/src/sdr/infrastructure/customer_repository.py` | DATABASE WORKER | 1 |
| `apps/sdr/src/sdr/infrastructure/conversation_repository.py` | DATABASE WORKER | 1 |
| `apps/sdr/src/sdr/infrastructure/evolution_client.py` | EVOLUTION INTEGRATION WORKER | 2 |
| `apps/sdr/src/sdr/infrastructure/document_repository.py` | DATABASE WORKER | 3 |
| `apps/sdr/src/sdr/infrastructure/notification_repository.py` | DATABASE WORKER | 3 |
| `apps/sdr/src/sdr/media/processor.py` | AI / LLM WORKER | 2 |
| `apps/sdr/src/sdr/media/audio_transcriber.py` | AI / LLM WORKER | 2 |
| `apps/sdr/src/sdr/media/image_describer.py` | AI / LLM WORKER | 2 |
| `apps/sdr/src/sdr/media/document_extractor.py` | AI / LLM WORKER | 3 |
| `apps/sdr/src/sdr/tools/inventory.py` | SDR CORE WORKER | 4 |
| `apps/sdr/src/sdr/tools/send_photos.py` | EVOLUTION INTEGRATION WORKER | 4 |
| ~~`apps/sdr/alembic/`~~ | — | — | **FORBIDDEN** — Prisma sole authority (ADR-003) |
| `apps/sdr/tests/unit/test_merge.py` | SDR CORE WORKER | 1 |
| `apps/sdr/tests/unit/test_decision.py` | SDR CORE WORKER | 1 |
| `apps/sdr/tests/unit/test_extractor.py` | AI / LLM WORKER | 1 |
| `apps/sdr/tests/unit/test_handoff.py` | SDR CORE WORKER | 3 |
| `apps/sdr/tests/unit/test_inventory_tool.py` | SDR CORE WORKER | 4 |
| `apps/sdr/tests/unit/test_document_extractor.py` | AI / LLM WORKER | 3 |
| `apps/sdr/tests/integration/test_evolution_client.py` | EVOLUTION INTEGRATION WORKER | 2 |
| `apps/sdr/tests/scenarios/` | QA WORKER | 7 |

## `apps/web/` (existing Next.js app — additive changes only)

| Path | Owner | Wave | Notes |
|------|-------|------|-------|
| `apps/web/prisma/schema.prisma` | DATABASE WORKER | 0 | Add new models only |
| `apps/web/prisma/migrations/20260826_sdr_*/` | DATABASE WORKER | 0 | New migrations |
| `apps/web/app/api/webhooks/sdr/route.ts` | WEB CRM WORKER | 0 | New file |
| `apps/web/features/sdr/` | WEB CRM WORKER | 0–6 | New directory |
| `apps/web/app/api/admin/sdr/` | WEB CRM WORKER | 3–6 | New directory |
| `apps/web/app/admin/(dashboard)/leads/[id]/page.tsx` | WEB CRM WORKER | 6 | Add juliaSummary section |
| `apps/web/app/admin/(dashboard)/leads/[id]/AssignLeadForm.tsx` | WEB CRM WORKER | 6 | Add "Assumir" button |
| `apps/web/app/admin/(dashboard)/leads/LeadsClient.tsx` | WEB CRM WORKER | 6 | Add temperature badge |
| `apps/web/features/lead/server/mutations.ts` | WEB CRM WORKER | 6 | Add `claimLeadAction` |
| `apps/web/components/admin/SdrNotificationBadge.tsx` | WEB CRM WORKER | 6 | New file |

## Root Level

| Path | Owner | Wave |
|------|-------|------|
| `docker-compose.sdr.yml` | SDR CORE WORKER | 0 |

## Files That MUST NOT Be Modified Without Explicit HITL Approval

| File | Reason |
|------|--------|
| `apps/web/app/api/webhooks/evolution/route.ts` | Catalog import webhook — do not touch |
| `apps/web/features/catalog-import/` | Catalog pipeline — separate concern |
| `apps/web/prisma/migrations/20260504000000_julia_integration/` | Applied migration — do not modify |
| Any existing applied migration | Database discipline — never rewrite |
| `apps/web/features/auth/server/rbac.ts` | RBAC contract — additive changes only |
| `julia_sdr_master_pack/` | Source of truth documentation — do not modify |
