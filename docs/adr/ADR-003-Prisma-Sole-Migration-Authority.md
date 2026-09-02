# ADR-003: Prisma Is the Sole Database Migration Authority

**Status**: Accepted (2026-08-26 AFK run)
**Supersedes**: Wave 0 suggestion in WORK_PACKAGES.md that mentioned Alembic for shared schema

## Context

The FacilCar monorepo already evolves the `facilcar` PostgreSQL schema via:

- `apps/web/prisma/schema.prisma`
- Prisma migrations under `apps/web/prisma/migrations/`

The SDR service is Python (ADR-001). An earlier Wave 0 draft suggested an Alembic scaffold under `apps/sdr/`. Two migration authorities for the same schema create drift risk and dual ownership.

## Decision

**Prisma is the single database migration authority for the MVP.**

- All additive schema changes (Conversation, Message, VisitInterest, SdrDocument, SdrNotification, Lead columns, etc.) go through Prisma.
- The Python SDR service **consumes** the schema (asyncpg / SQLAlchemy / plain SQL).
- **Do not** create Alembic migrations for shared FacilCar tables.
- If an empty Alembic scaffold appears, remove it or mark it non-authoritative.

## Consequences

- DATABASE WORKER owns Prisma schema + migrations only.
- Python `db.py` is a connection/query layer, not a migration engine.
- `FILE_OWNERSHIP.md` and `WORK_PACKAGES.md` must not assign Alembic as schema authority.
- Staging/production apply schema via `prisma migrate deploy` (or existing project workflow).

## Alternatives Rejected

- Dual Prisma + Alembic for the same tables — rejected (drift).
- Python-owned schema with Prisma as follower — rejected (web app already owns CRM tables).
