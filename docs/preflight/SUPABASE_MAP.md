# SUPABASE_MAP — Production Investigation (READ-ONLY)

> Date: 2026-08-25
> Method: READ-ONLY via Supabase MCP (`plugin-supabase-supabase`)

## Project Resolution

Two Supabase project references exist in the repository:

| Path | Ref | Name | Access |
|------|-----|------|--------|
| `supabase/.temp/linked-project.json` | `munnfnfudrsoblwgivjn` | facilcar | Legacy n8n/RAG project — **PAUSED**. Ignore. Do not reactivate. |
| `apps/web/supabase/.temp/linked-project.json` | `oulknepjqhyiyjbiuqtg` | facilcar | ✅ Accessible — AUTHORITATIVE PRODUCTION |

**Resolution (HITL-001 RESOLVED 2026-08-26)**: `oulknepjqhyiyjbiuqtg` is the authoritative production project. `munnfnfudrsoblwgivjn` is a paused legacy n8n/experimental project — **not staging**, not a dependency. New SDR is independent of it. Cloud staging is ENVIRONMENT_PENDING until a new project is provisioned.

**Both** projects belong to org `ucnzpvcszmrplxllgchg`.

---

## Schema: `facilcar`

All 16 tables confirmed present and matching Prisma schema:

| Table | RLS | Notes |
|-------|-----|-------|
| BlogPost | **OFF** | Content table |
| Brand | **OFF** | Reference data |
| CatalogImportEvent | **OFF** | Catalog pipeline |
| CatalogImportItem | **OFF** | Catalog pipeline |
| CatalogMediaAsset | **OFF** | Catalog pipeline |
| CatalogMediaBlob | **OFF** | Catalog pipeline |
| Customer | **OFF** | ⚠️ Contains PII (phone, email) |
| FinancingRequest | **OFF** | ⚠️ Contains CPF, income, birth date |
| Lead | **OFF** | ⚠️ Contains phone, email |
| Page | **OFF** | Content table |
| SellRequest | **OFF** | ⚠️ Vehicle data |
| SiteSettings | **OFF** | Config |
| User | **OFF** | ⚠️ Contains passwordHash |
| Vehicle | **OFF** | Catalog |
| VehicleFeature | **OFF** | Catalog |
| VehicleImage | **OFF** | Media URLs |

**⚠️ CRITICAL SECURITY FINDING**: RLS is **disabled on all 16 tables**. The web app uses Prisma server-side so Data API exposure depends entirely on whether direct Supabase Data API access is enabled and whether service_role is used. Before go-live:
- Confirm service_role key is NEVER sent to client
- Confirm Supabase Data API (REST/GraphQL/Realtime) is not enabled for anonymous access to `facilcar` schema
- Plan RLS enablement (non-blocking for SDR implementation, required before production go-live)

---

## Extensions

| Extension | Installed |
|-----------|-----------|
| pgcrypto | ✅ v1.3 |
| uuid-ossp | ✅ v1.1 |
| vector (pgvector) | **NOT installed** |
| pg_cron | NOT installed |
| pg_net | NOT installed |

**pgvector implication**: RAG with Supabase vector store is NOT available without first running `CREATE EXTENSION IF NOT EXISTS vector;`. The architecture recommendation avoids mandatory RAG in MVP, so this is non-blocking. If RAG is needed later, the extension must be installed via Supabase dashboard (no `alter system` access).

---

## Storage Buckets

| Bucket | Public | Status |
|--------|--------|--------|
| `vehicle-images` | ✅ Yes | Active — 42 objects uploaded |

**Missing**: No private bucket for SDR documents (CNH, CRLV, income proof, residence proof).

**Required additive work**: Create `sdr-documents` private bucket with signed URL policy.

**Existing bucket policies** (from migration `20250324121000_facilcar_vehicle_images_bucket`):
- `facilcar_vehicle_images_public_read` — public SELECT
- `facilcar_vehicle_images_authenticated_insert` — authenticated INSERT
- `facilcar_vehicle_images_authenticated_update` / DELETE — authenticated

---

## Production Data State (2026-08-25)

| Table | Row Count | Notes |
|-------|-----------|-------|
| Vehicle | 41 (40 PUBLISHED, 1 DRAFT) | All CAR type |
| VehicleImage | ~44 | ~1 per vehicle |
| Brand | 14+ | Fiat, Chevrolet, Ford, etc. |
| Customer | 0 | Empty — schema live |
| Lead | 0 | Empty — schema live |
| FinancingRequest | 0 | Empty |
| SellRequest | 0 | Empty |
| User | 2 | Milton Barrios (ADMIN) + admin demo (SUPER_ADMIN) |
| CatalogImportEvent | ~50 | Catalog import history |
| CatalogImportItem | 46 | 44 IMPORTED, 2 FAILED |

---

## Migrations Applied

All 8 migrations confirmed applied:
1. `20250324120000_facilcar_schema_initial` — Full initial schema
2. `20250324121000_facilcar_vehicle_images_bucket` — Storage bucket + RLS policies
3. `20250324122000_facilcar_vehicle_images_anon_seed_upload` — Anon upload policy (temporary/seed)
4. `20330330210000_facilcar_lead_internal_note_financing_extra_fields` — Financing extras
5. `20260504000000_julia_integration` — Julia enum extensions + Vehicle fields
6. `20260725120000_facilcar_site_public_theme` — SiteSettings.publicTheme
7. `20260725130000_customer_lead_deleted` — Lead soft-delete
8. `20260812120000_catalog_import_staging` — CatalogImport* tables

---

## SDR Additive Migrations Required

| Migration | Purpose | Blocking? |
|-----------|---------|-----------|
| `Conversation` / `Thread` table | WhatsApp thread state, bot/human flag | Wave 0 — CRITICAL |
| `Message` table | Per-message storage | Wave 0 — CRITICAL |
| `VisitInterest` table | Simple visit intent record | Wave 2 |
| `SdrDocument` table | Uploaded document metadata + extracted fields | Wave 3 |
| `SdrNotification` table | Queue for web panel notifications | Wave 4 |
| `sdr-documents` private bucket | Private storage for sensitive docs | Wave 3 |
| Enable RLS on PII tables | Security hardening | Pre-go-live |

All migrations must be ADDITIVE. No modifications to existing tables/enums except via new additive columns with `ADD COLUMN IF NOT EXISTS`.

---

## Staging Project

HITL-001 RESOLVED: `munnfnfudrsoblwgivjn` is **paused legacy** — not staging. Do not reactivate for MVP.

Staging remains an approved architecture goal (D-003). Until a new Supabase project is provisioned by a human (account/billing):

- Use local Supabase / local Postgres for integration
- Document cloud staging as `ENVIRONMENT_PENDING`
- Seed scripts for public catalog only (no PII)

Staging must contain:
- ✅ Catalog (Vehicles, Brands, VehicleImages — public data only)
- ✅ SiteSettings
- ✅ Admin user (non-production credentials)
- ❌ No Customer PII
- ❌ No real Lead data
- ❌ No sensitive documents
- ❌ No dependency on paused project `munnfnfudrsoblwgivjn`
