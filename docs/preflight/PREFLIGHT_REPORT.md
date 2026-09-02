# PREFLIGHT REPORT — Júlia SDR

> Date: 2026-08-25
> Author: Pre-flight Investigation Run
> Status: **READY_WITH_NON_BLOCKING_GAPS**

---

## Executive Summary

The FacilCar monorepo is ready for SDR implementation to begin.

The existing CRM, Lead pipeline, customer model, vehicle catalog, Evolution API integration, and OpenAI patterns provide a solid foundation. The three HITL questions identified (staging project identity, commercial playbook owner, production webhook routing) are all deferred to later waves and do not block any Wave 0–7 development work.

**Major blockers**: None.

**Major risks**:
- RLS disabled on all production tables (security — pre-go-live fix required)
- Commercial playbook content does not exist yet (quality — required before pilot)
- Vehicle data gaps (mileage, color, km missing on most stock)
- No CI/CD for Python service

**Recommended architecture**: FastAPI + Python worker + Redis + Supabase/Postgres. No Temporal, no Kubernetes, no RAG for MVP.

**Implementation readiness**: `READY_WITH_NON_BLOCKING_GAPS`

---

## Verified Existing Capabilities (Reusable)

| Capability | Location | Notes |
|-----------|----------|-------|
| Lead CRUD + status lifecycle | `features/lead/server/mutations.ts` | Includes WON→SOLD side-effect |
| Customer upsert by phone | `features/customer/server/upsert.ts` | Correct unique-by-phone invariant |
| Vehicle catalog query (PUBLISHED only) | `features/catalog/server/queries.ts` | Correct stock rule |
| RBAC (roles, section guards) | `features/auth/server/rbac.ts` | SUPER_ADMIN, ADMIN, LEAD_MANAGER defined |
| Lead assignment (assignedToUserId) | `features/lead/server/mutations.ts` | Seller assignment exists |
| Soft delete for leads | `Lead.deletedAt` | Already implemented |
| Lead detail page with FinancingRequest | `app/admin/(dashboard)/leads/[id]/page.tsx` | CPF masking already implemented |
| Kanban + list views | `components/admin/Kanban/` | Drag-drop lead status already works |
| Prisma schema + migrations | `prisma/schema.prisma` | Versioned, clean |
| Julia migration applied | `20260504000000_julia_integration` | REFINANCING, TRADE_IN, CONSIGNMENT, WHATSAPP source |
| Evolution webhook parse | `features/catalog-import/server/evolution-parse.ts` | Production-proven, reusable |
| JID normalization | `features/catalog-import/server/normalize-jid.ts` | Group detection, LID handling, device suffix |
| OpenAI structured extraction | `features/catalog-import/server/openai-extract.ts` | json_schema, strict, temperature=0 |
| S3-compatible storage upload | `features/storage/server/` | Works with Supabase Storage + R2 |
| Evolution API v2.3.7 docker stack | `docker-compose.evolution.yml` | Port 8081, own Postgres+Redis |
| SiteSettings (address, phone, email) | `model SiteSettings` | Official store contact info |
| `metadataJson` on Lead | `Lead.metadataJson (Json?)` | Free-form slots without migration |

---

## Required Additive Work

### Database (New Tables — Additive Only)

| Table | Purpose | Wave |
|-------|---------|------|
| `Conversation` | WhatsApp thread state machine | 0 |
| `Message` | Per-message log with deduplication | 0 |
| `VisitInterest` | Simple visit interest (no calendar) | 2 |
| `SdrDocument` | Uploaded document metadata + extracted fields | 3 |
| `SdrNotification` | Notification queue for web panel | 4 |

### New Software Components

| Component | Language | Wave |
|-----------|---------|------|
| `apps/sdr/` Python FastAPI service | Python 3.12 | 0 |
| SDR webhook endpoint (`/api/webhooks/sdr/`) | TypeScript (Next.js) | 0 |
| Conversation orchestrator | Python | 1 |
| State merge engine (deterministic) | Python | 1 |
| Decision engine (deterministic) | Python | 1 |
| Understanding engine (LLM→TurnFacts) | Python | 1 |
| Response composer (LLM→bubbles) | Python | 1 |
| Evolution ingress adapter (Python) | Python | 2 |
| Media processor (audio transcription, Vision) | Python | 2 |
| Document extractor | Python | 3 |
| Handoff + lead creation logic | Python | 3 |
| Web panel: notifications + "Assumir" button | TypeScript (Next.js) | 4 |
| Web panel: SDR conversation summary display | TypeScript (Next.js) | 4 |
| Private document bucket (`sdr-documents`) | Supabase Storage | 3 |
| Signed URL admin endpoint | TypeScript (Next.js) | 3 |

### Environment / Infrastructure

| Item | Wave |
|------|------|
| `apps/sdr/.env.example` | 0 |
| `docker-compose.sdr.yml` | 0 |
| `apps/sdr/pyproject.toml` | 0 |
| `apps/sdr/alembic/` migrations | 0 |
| `JULIA_ENABLED` feature flag | 1 |
| `sdr-documents` Supabase bucket | 3 |
| Staging Supabase project population | 8 |

---

## Conflicts Found

| ID | Conflict | Classification |
|----|---------|----------------|
| C-001 | `pnpm-lock.yaml` (empty) vs `package-lock.json` | `NON_BLOCKING_TECHNICAL_DECISION` |
| C-002 | Two Supabase `.temp` project refs | `HITL_REQUIRED` (HITL-001) |
| C-003 | LeadStatus extra states vs SDR docs | `RESOLVED_FROM_EVIDENCE` |
| C-004 | HANDOFF.md says "no migrations folder" | `RESOLVED_FROM_EVIDENCE` (outdated doc) |
| C-005 | Vehicle Julia fields exist but empty | `NON_BLOCKING_TECHNICAL_DECISION` |
| C-006 | Production WA number vs dev number | `RESOLVED_FROM_EVIDENCE` |

---

## MVP Architecture Recommendation

```
WhatsApp
  ↓ (Evolution webhook v2.3.7)
[Ingress — Next.js /api/webhooks/sdr]  ← MVP: relay via Vercel
  ↓ (DB insert + enqueue)
[SDR Worker — Python FastAPI queue poller]
  ↓
[Conversation Orchestrator]
  ├─ [Debounce (Redis, ~1.5s)]
  ├─ [Lock per thread (Redis)]
  ├─ [Idempotency check (provider_message_id)]
  └─ [Media Processor] (audio→Whisper, image/doc→Vision)
       ↓
[Understanding Engine]
  → LLM (gpt-4.1-mini) → TurnFacts JSON
       ↓
[State Merge — DETERMINISTIC]
  → new_state = merge(prev_state, turn_facts)
  → Postgres Conversation + Lead update
       ↓
[Decision Engine — DETERMINISTIC]
  → action: ask_info | show_offers | send_photos | handoff | ...
       ↓
[Knowledge Router / Tool Execution]
  ├─ Vehicle lookup (Prisma, PUBLISHED only)
  ├─ SiteSettings (address, hours)
  └─ Lead/Customer upsert
       ↓
[Response Composer]
  → LLM (gpt-4.1-mini) → 1–3 short pt-BR bubbles
       ↓
[Response Validator]
  → check: no invented price/rate/promise
       ↓
[Evolution API — sendText per bubble]
  ↓
WhatsApp
```

**Persistence**: Supabase/Postgres (source of truth)
**Ephemeral**: Redis (locks, debounce, idempotency keys)
**Storage**: Supabase Storage (private bucket for documents)
**LLM**: OpenAI gpt-4.1-mini (default) / gpt-4o (Vision)
**No Temporal**, **No RAG for MVP**, **No Kubernetes**

---

## Data Model Changes (Additive — no SQL yet)

### New: `Conversation` (Thread)
```
id, phone (indexed), instanceName, botStatus (BOT_ACTIVE|QUALIFYING|READY_FOR_HANDOFF|HANDOFF_SENT|HUMAN_ACTIVE|HUMAN_CLOSED)
language (pt-BR|es|unknown), accumulatedSummary, lastMessageAt
activeLeadIds (String[]) -- JSON array of Lead IDs
handoffAt, createdAt, updatedAt
```

### New: `Message`
```
id, conversationId → Conversation
providerMessageId (unique per instance), direction (INBOUND|OUTBOUND)
contentType (text|audio|image|document|video|sticker)
text?, mediaStorageKey?, mediaType?, transcription?
fromMe, isHumanSent (bool — true if seller, false if bot)
language?, turnFactsJson?, createdAt, processedAt
```

### New: `VisitInterest`
```
id, leadId → Lead, conversationId → Conversation
dateHint (free text or Date?), period?, notes?, createdAt
```

### New: `SdrDocument`
```
id, leadId → Lead, conversationId → Conversation
documentType (CNH|CRLV|INCOME_PROOF|RESIDENCE_PROOF|OTHER)
storageKey (private), mimeType, byteSize
extractedJson (Json?), extractionStatus (PENDING|DONE|FAILED)
retentionPolicy (PERMANENT|180_DAYS), createdAt
```

### New: `SdrNotification`
```
id, leadId → Lead, type (NEW_QUALIFIED|NEW_HOT_LEAD)
seenByUserId?, seenAt?, createdAt
```

### Additive: `Lead.juliaSummary (String?)`
Short structured summary generated on handoff. Displayed in web panel.

### Additive: `Lead.temperature (HOT|WARM|COLD)?`
Visual indicator, never handoff condition.

---

## Security / Privacy

- All sensitive document originals stored in private `sdr-documents` bucket
- LEAD_MANAGER role cannot access original files (signed URL admin-only)
- CPF/CNPJ masked in UI (existing pattern in `lead/[id]/page.tsx`)
- RLS currently disabled — must be enabled before production go-live
- OpenAI D-004: permitted for documents; check data retention policy
- No PII in logs (mask before logging)

---

## Local Runtime

See `LOCAL_STACK.md`. Budget: 4 CPU / 8 GB RAM. Fits comfortably. Recommended services:
Postgres + Redis + Evolution + SDR API + SDR Worker (~2.1 GB RAM total).

---

## Staging

Pending HITL-001 (staging project identity). Once resolved:
- Apply migrations from Wave 0 to staging
- Seed with 40 vehicles (public catalog snapshot, no PII)
- Create test admin user with different credentials
- Connect SDR dev number (`5545988432998`) to staging Evolution instance

---

## Production

Target: Hostinger VPS (Docker Compose). Not yet purchased. Architecture is portable — no cloud-specific dependencies except Supabase (can point to production Supabase project). Next.js app stays on Vercel (zero migration needed).

---

## Vercel Impact

**None.** Adding `apps/sdr/` to the monorepo has zero impact on the Vercel deployment. See `VERCEL_IMPACT.md` for full analysis.

---

## Cost Risk

Estimated AI cost: R$55–80/month for MVP volume. Infrastructure (VPS ~R$150-250/month estimate for Hostinger). Total incremental ≤ R$350/month — within the R$500 budget. See `OPENAI_SURFACE.md` for detailed breakdown.

---

## Implementation Readiness

**`READY_WITH_NON_BLOCKING_GAPS`**

Three HITL questions documented in `HITL_REQUIRED.md`. None block Waves 0–7.

Recommended next action: Launch multi-agent implementation run starting with Wave 0.
