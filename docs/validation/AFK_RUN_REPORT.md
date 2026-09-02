# AFK RUN REPORT — Júlia SDR

> Date: 2026-08-26  
> Branch: `develop` (dirty tree preserved — no destructive git; no push)  
> Status: **COMPLETE_WITH_EXTERNAL_GATES**

## HITL resolutions applied

| ID | Resolution |
|----|------------|
| HITL-001 | `munnfnfudrsoblwgivjn` = paused legacy n8n/RAG — **ignored**; not staging |
| HITL-002 | Milton validates commercial playbook before production |
| HITL-003 | MVP = Vercel relay; future = direct VPS; config-driven |

## Architecture implemented

```
Evolution → Next.js /api/webhooks/sdr (Vercel relay)
  → Conversation + Message (Prisma)
  → Python worker (poll PENDING)
  → extract TurnFacts → deterministic merge → decide → compose
  → Lead QUALIFIED + SdrNotification + one confirmation bubble
  → bot silence / fromMe → HUMAN_ACTIVE
```

- Prisma = sole migration authority (ADR-003)
- Python FastAPI in `apps/sdr/` (ADR-001)
- Redis ephemeral only
- No Alembic, no RAG, no Temporal, no paused Supabase dependency

## Waves completed (code)

| Wave | Status | Notes |
|------|--------|-------|
| 0 | DONE | Schema, FastAPI scaffold, webhook relay |
| 1 | DONE | Domain merge/decision/orchestrator/understanding |
| 2 | DONE | Evolution client, media processor stubs |
| 3 | DONE | Document extractor/storage/signed URL (admin) |
| 4 | DONE | Inventory PUBLISHED-only + photos/location tools |
| 5 | DONE | 6 flows via domain + golden scenarios |
| 6 | DONE | Notifications API, Assumir claim, juliaSummary UI |
| 7 | DONE | 80 pytest incl. 10 goldens; vitest SDR; typecheck; build |
| 8 | ENVIRONMENT_PENDING | Cloud staging project not provisioned |
| 9 | EXTERNAL_GATES | VPS purchase, Milton sign-off, RLS prod, WhatsApp QR |

## Migrations added

- `apps/web/prisma/migrations/20260826120000_sdr_core/` — Conversation, Message, VisitInterest, SdrDocument, SdrNotification + Lead columns

Applied on local Docker Postgres via raw SQL (DB had prior db:push history — `migrate deploy` needs baseline before prod).

## Key endpoints

| Endpoint | Role |
|----------|------|
| `POST /api/webhooks/sdr` | Evolution relay (Vercel) |
| `GET/POST apps/sdr :8000/health`, `/webhook/evolution` | Python API |
| `GET /api/admin/sdr/notifications` | Polling notifications |
| `GET /api/admin/sdr/documents/[id]/signed-url` | Admin-only originals |

## Env vars (new)

See `apps/sdr/.env.example` and additive lines in `apps/web/.env.example`:  
`SDR_WEBHOOK_SECRET`, `JULIA_ENABLED`, `SDR_API_URL`, `SDR_TRANSPORT_MODE`, OpenAI/Evolution/Redis/Storage.

## Tests

| Suite | Result |
|-------|--------|
| `apps/sdr` pytest | **80 passed** |
| `apps/web` vitest (sdr) | **9 passed** |
| `apps/web` typecheck | **pass** |
| `apps/web` build | **pass** (includes SDR routes) |

## Deviations from plan

1. No Alembic (ADR-003 correction).
2. Local migrate deploy blocked by P3005 (non-empty DB without migration history) — SQL applied directly for local; production needs careful `migrate deploy` / baseline.
3. Cloud staging deferred (`docs/validation/STAGING_ENVIRONMENT_PENDING.md`).
4. Heuristic TurnFacts used when `OPENAI_API_KEY` absent (live LLM optional).
5. Private bucket `sdr-documents` must still be created in Supabase dashboard (ops step).

## Unresolved / external

- Hostinger VPS not purchased
- Staging Supabase project not created
- WhatsApp QR for `5545988432998` may need human scan
- Milton commercial sign-off
- RLS enablement on production tables (test locally first)
- Create private Storage bucket `sdr-documents`

## Security status

- Service-role must remain server-only (pre-existing risk: RLS off on facilcar)
- Document signed URL gated to ADMIN/SUPER_ADMIN
- Retention helpers + dry-run philosophy (no destructive auto-cron yet)
- Kill switch `JULIA_ENABLED`

## Cost

- Structured for gpt-4.1-mini default + Vision/Whisper as needed
- No live OpenAI burn in CI (mocks/heuristics)

## First file to read on return

`docs/validation/MANUAL_VALIDATION_CHECKLIST.md`
