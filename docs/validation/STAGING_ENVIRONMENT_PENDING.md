# Staging Environment — ENVIRONMENT_PENDING

HITL-001 resolved: paused project `munnfnfudrsoblwgivjn` is **not** staging.

## What is ready in-repo
- Prisma migrations for SDR tables (Wave 0+)
- Seed strategy: public catalog + SiteSettings only
- Local Docker / Supabase CLI for integration tests

## What requires a human
1. Create new Supabase project `facilcar-staging` (or equivalent name) in org
2. Set `DATABASE_URL` / keys in staging env secrets
3. `prisma migrate deploy` against staging
4. Seed catalog snapshot (no PII)
5. Point Evolution **dev** instance to test number `5545988432998` + Vercel preview or staging webhook URL

## Do not
- Activate `munnfnfudrsoblwgivjn`
- Copy production Customer/Lead/documents
- Use production WhatsApp for ordinary tests
