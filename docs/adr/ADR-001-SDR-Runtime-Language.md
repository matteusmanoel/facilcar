# ADR-001: SDR Runtime Language — Python (FastAPI)

**Status**: Accepted (confirmed from julia_sdr_master_pack/docs/09_ARCHITECTURE.md)
**Date**: 2026-08-25

## Context

The existing FacilCar web app is TypeScript/Next.js. The SDR requires:
- An async HTTP ingress (webhook receiver)
- A background worker (conversation processing)
- AI/ML integrations (OpenAI, Whisper, Vision)
- Redis operations (locks, debounce)

## Decision

The SDR service (`apps/sdr`) is implemented in **Python 3.12** using **FastAPI**.

## Rationale

1. **OpenAI Python SDK** is the primary, best-maintained SDK with full async support.
2. **FastAPI** is well-suited for async webhook receivers and background workers.
3. **Separation of concerns**: Python service is deployed on VPS separately from Vercel-hosted Next.js.
4. **Existing TypeScript app continues unchanged** — zero migration risk.
5. **Catalog-import precedent**: The existing TypeScript worker pattern is monolingual to the web app and harder to maintain separately. Python is standard for AI-heavy workloads.

## Consequences

- Requires Python 3.12 on VPS
- Docker container for the SDR service
- Prisma is NOT used in Python — direct asyncpg or SQLAlchemy + raw SQL for DB access
- The Prisma schema remains the canonical schema definition (TypeScript app runs migrations)
- Python alembic manages Python-side migration tracking (synced with Prisma migrations)

## Alternatives Considered

- **TypeScript worker** (tsx): Would coexist naturally with apps/web but lacks quality async AI tooling. More coupling with Vercel deployment. Rejected.
- **Separate repository**: Clean isolation but adds deployment complexity. Rejected for MVP in favor of monorepo.
