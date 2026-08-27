# WORK PACKAGES — Multi-Agent Implementation

> Each WP has a single owner role. No two WPs touch the same file concurrently.
> Parallel = can run simultaneously. Sequential = must wait for dependency.

---

## Wave 0 Work Packages

### WP-000: Database Migrations
**Owner**: DATABASE WORKER
**Parallel**: Yes (with WP-001)
**Depends on**: Nothing

**Objective**: Create additive migrations for Conversation, Message, VisitInterest, SdrDocument, SdrNotification tables + Lead additive columns.

**Files/Directories** (Prisma = sole migration authority — see ADR-003):
- `apps/web/prisma/schema.prisma` — ADD Conversation, Message, VisitInterest, SdrDocument, SdrNotification models + Lead additive columns
- `apps/web/prisma/migrations/<timestamp>_sdr_*/migration.sql` (new additive migrations)
- **NO** `apps/sdr/alembic/` — do not create a second migration authority

**Input contract**:
- Prisma schema with new models
- All additive (`ADD COLUMN IF NOT EXISTS`, new tables only)
- No modification to existing tables beyond new columns on `Lead`

**Output contract**:
- Prisma client regenerated
- TypeScript types for Conversation, Message available in `apps/web`
- Python SDR consumes schema via asyncpg/SQLAlchemy/plain SQL (no Alembic for shared tables)

**Tests required**:
- Migration applies cleanly on a fresh DB
- Migration is idempotent (re-running does not fail)

**Acceptance criteria**:
- [ ] `supabase db push` or `prisma migrate deploy` succeeds on staging DB
- [ ] New tables visible in `pg_tables`
- [ ] Existing 16 tables untouched

**Rollback**: `prisma migrate revert` (remove new tables — no data loss since they're new)

---

### WP-001: Python Service Scaffold
**Owner**: SDR CORE WORKER
**Parallel**: Yes (with WP-000)
**Depends on**: Nothing

**Objective**: Create `apps/sdr/` Python FastAPI service skeleton with correct project structure, env config, and Docker setup.

**Files/Directories**:
- `apps/sdr/` (new directory)
- `apps/sdr/pyproject.toml` (Python 3.12, FastAPI, httpx, redis, asyncpg/sqlalchemy, openai, pydantic — NO alembic for shared schema)
- `apps/sdr/uv.lock` or `requirements.txt`
- `apps/sdr/.env.example`
- `apps/sdr/Dockerfile`
- `apps/sdr/src/sdr/__init__.py`
- `apps/sdr/src/sdr/main.py` (FastAPI app factory)
- `apps/sdr/src/sdr/config.py` (Pydantic Settings)
- `apps/sdr/src/sdr/db.py` (async Postgres connection)
- `apps/sdr/src/sdr/redis_client.py`
- `apps/sdr/src/sdr/api/__init__.py`
- `apps/sdr/src/sdr/api/health.py` (GET /health)
- `apps/sdr/src/sdr/api/webhook.py` (POST /webhook/evolution)
- `apps/sdr/tests/__init__.py`
- `apps/sdr/tests/conftest.py`
- `docker-compose.sdr.yml` (new at repo root) — sdr-api + sdr-worker + redis services

**Output contract**:
- `GET /health` returns 200
- `POST /webhook/evolution` returns 200 for valid payloads, 401 for missing secret
- Service starts cleanly with `.env.example` values

**Tests required**:
- Health endpoint returns 200
- Webhook returns 401 without secret
- Webhook returns 200 with valid secret

**Acceptance criteria**:
- [ ] `docker-compose -f docker-compose.sdr.yml up -d` starts all services
- [ ] `GET http://localhost:8000/health` → `{"ok": true}`

---

### WP-002: Webhook Relay in Next.js
**Owner**: WEB CRM WORKER
**Parallel**: Yes (with WP-000, WP-001)
**Depends on**: Nothing (but uses models from WP-000 output)

**Objective**: Create `apps/web/app/api/webhooks/sdr/route.ts` that receives Evolution webhooks, performs idempotency check, creates Conversation+Message rows, and optionally relays to Python SDR service.

**Files/Directories**:
- `apps/web/app/api/webhooks/sdr/route.ts` (new)
- `apps/web/features/sdr/server/ingest.ts` (new — DB write logic)
- `apps/web/features/sdr/server/jid-guard.ts` (new — reuses normalize-jid, adds group block)

**Input contract**:
- Reuse `normalizeRemoteJid`, `peerIdentityCandidates`, `preferredPeerJid` from `features/catalog-import/server/normalize-jid.ts`
- Reuse message extraction pattern from `evolution-parse.ts`
- `SDR_WEBHOOK_SECRET` env var for auth

**Output contract**:
- Groups (`@g.us`) → 200 `{ok: true, handled: 0, reason: "group_ignored"}`
- Duplicate messages → 200 `{ok: true, deduped: true}`
- Valid new message → 200 `{ok: true, conversationId, messageId}`
- `fromMe=true` + unknown sender ID → mark Conversation HUMAN_ACTIVE

**Tests required**:
- Group message returns handled=0
- Duplicate returns deduped=true
- fromMe human marks HUMAN_ACTIVE
- Missing secret returns 401

**Acceptance criteria**:
- [ ] Evolution webhook points to `/api/webhooks/sdr`
- [ ] New message from test number creates Conversation + Message row
- [ ] Group message creates no rows

---

## Wave 1 Work Packages

### WP-100: Domain Types + State Merge Engine
**Owner**: SDR CORE WORKER
**Parallel**: No (foundation for WP-101–104)
**Depends on**: WP-000 (schema), WP-001 (Python scaffold)

**Files**:
- `apps/sdr/src/sdr/domain/types.py` — TurnFacts, ConversationState, BusinessIntent, HandoffSignals
- `apps/sdr/src/sdr/domain/merge.py` — `deterministic_merge(state, turn_facts) → new_state`
- `apps/sdr/src/sdr/domain/qualifications.py` — triage sufficiency rules per LeadType
- `apps/sdr/tests/unit/test_merge.py` — mandatory unit tests

**Key invariants to test**:
- `merge(state with CPF, TurnFacts without CPF) → CPF preserved`
- `unknown != false` (missing signal ≠ false signal)
- Explicit correction overwrites prior value
- `high_purchase_intent=True` with known model → READY_FOR_HANDOFF

---

### WP-101: Understanding Engine (LLM→TurnFacts)
**Owner**: AI / LLM WORKER
**Parallel**: Yes (with WP-102)
**Depends on**: WP-100

**Files**:
- `apps/sdr/src/sdr/understanding/extractor.py` — `extract_turn_facts(text, state_summary) → TurnFacts`
- `apps/sdr/src/sdr/understanding/prompts.py` — system prompt for TurnFacts extraction
- `apps/sdr/src/sdr/understanding/response_composer.py` — `compose_response(state, action, context) → List[str]`
- `apps/sdr/src/sdr/understanding/persona_prompts.py` — Júlia persona prompt
- `apps/sdr/tests/unit/test_extractor.py`

**Model**: `SDR_UNDERSTANDING_MODEL` env (default: gpt-4.1-mini)
**Format**: `response_format: json_schema`, `strict: true`, `temperature: 0`

---

### WP-102: Decision Engine
**Owner**: SDR CORE WORKER
**Parallel**: Yes (with WP-101)
**Depends on**: WP-100

**Files**:
- `apps/sdr/src/sdr/domain/decision.py` — `decide(state) → Action`
- `apps/sdr/src/sdr/domain/handoff.py` — handoff trigger rules
- `apps/sdr/tests/unit/test_decision.py`

**Rules implemented**:
- Explicit vendor request → `handoff_vendor`
- Explicit offer → `handoff_vendor`
- High purchase intent + sufficient triage → `handoff_vendor`
- Visit intent → `register_visit_interest`
- Unknown model + budget → `show_offers`
- Insufficient info → `ask_info` (one question at a time)

---

### WP-103: Conversation Orchestrator
**Owner**: SDR CORE WORKER
**Parallel**: No (integrates WP-101, WP-102)
**Depends on**: WP-101, WP-102

**Files**:
- `apps/sdr/src/sdr/orchestrator.py` — main turn processing pipeline
- `apps/sdr/src/sdr/worker.py` — polling loop
- `apps/sdr/src/sdr/locks.py` — Redis lock per conversation (phone-level)
- `apps/sdr/src/sdr/debounce.py` — configurable debounce window

**Pipeline**:
1. Acquire Redis lock (phone-level, TTL=60s)
2. Debounce window (1.5s default, configurable)
3. Load conversation state from DB
4. Run understanding engine → TurnFacts
5. Run state merge
6. Run decision engine → Action
7. Execute action (tools, DB writes)
8. Compose response
9. Send via Evolution API
10. Save new state, release lock

---

### WP-104: Lead + Customer Persistence
**Owner**: DATABASE WORKER
**Parallel**: Yes (with WP-103, after WP-000)
**Depends on**: WP-000, WP-100

**Files**:
- `apps/sdr/src/sdr/infrastructure/lead_repository.py`
- `apps/sdr/src/sdr/infrastructure/customer_repository.py`
- `apps/sdr/src/sdr/infrastructure/conversation_repository.py`

**Rules**:
- Customer upsert by phone (digits only) — matches existing `resolveCustomerForLead` logic
- Lead created only after commercial intent (not on greeting)
- Handoff: Lead status → QUALIFIED, `juliaSummary` set, `assignedToUserId` = null (queue)

---

## Wave 2 Work Packages

### WP-200: Evolution Python Client
**Owner**: EVOLUTION INTEGRATION WORKER
**Parallel**: Yes (with WP-201)
**Depends on**: WP-001

**Files**:
- `apps/sdr/src/sdr/infrastructure/evolution_client.py` — send text, send media, download media
- `apps/sdr/tests/integration/test_evolution_client.py`

---

### WP-201: Media Processor
**Owner**: AI / LLM WORKER
**Parallel**: Yes (with WP-200)
**Depends on**: WP-001

**Files**:
- `apps/sdr/src/sdr/media/processor.py` — route by type: audio→transcribe, image→describe, doc→store
- `apps/sdr/src/sdr/media/audio_transcriber.py` — OpenAI Whisper
- `apps/sdr/src/sdr/media/image_describer.py` — OpenAI Vision (no mechanical/value claims)
- `apps/sdr/tests/unit/test_media_processor.py`

---

## Wave 3 Work Packages

### WP-300: Document Extractor
**Owner**: AI / LLM WORKER
**Parallel**: No
**Depends on**: WP-201, WP-000 (SdrDocument table)

**Files**:
- `apps/sdr/src/sdr/media/document_extractor.py` — extract CPF, name, birth_date, plate, etc.
- `apps/sdr/src/sdr/infrastructure/document_repository.py`
- `apps/sdr/tests/unit/test_document_extractor.py` — includes conflict detection test

---

### WP-301: Handoff Pipeline
**Owner**: SDR CORE WORKER
**Parallel**: No
**Depends on**: WP-102, WP-104

**Files**:
- `apps/sdr/src/sdr/domain/handoff.py` (extend from Wave 1)
- `apps/sdr/src/sdr/infrastructure/notification_repository.py` — create SdrNotification
- `apps/sdr/tests/unit/test_handoff.py` — irreversibility, one message, silence

---

### WP-302: Private Document Storage (Web)
**Owner**: WEB CRM WORKER
**Parallel**: Yes (with WP-301)
**Depends on**: WP-000

**Files**:
- `apps/web/app/api/admin/sdr/documents/[id]/signed-url/route.ts` — ADMIN-only signed URL
- `apps/web/features/sdr/server/document-access.ts`

---

## Wave 4 Work Packages

### WP-400: Inventory Tool
**Owner**: SDR CORE WORKER
**Parallel**: Yes (with WP-401)
**Depends on**: WP-103

**Files**:
- `apps/sdr/src/sdr/tools/inventory.py` — query PUBLISHED vehicles, return ≤3 alternatives
- `apps/sdr/tests/unit/test_inventory_tool.py` — published-only, no fabrication

---

### WP-401: Photo Sending Tool
**Owner**: EVOLUTION INTEGRATION WORKER
**Parallel**: Yes (with WP-400)
**Depends on**: WP-200

**Files**:
- `apps/sdr/src/sdr/tools/send_photos.py` — fetch VehicleImage URLs, send via Evolution

---

## Wave 6 Work Packages

### WP-600: Notification Center (Web)
**Owner**: WEB CRM WORKER
**Parallel**: No
**Depends on**: WP-301, WP-000 (SdrNotification)

**Files**:
- `apps/web/app/admin/(dashboard)/leads/page.tsx` — add new-lead badge
- `apps/web/components/admin/SdrNotificationBadge.tsx` (new)
- `apps/web/app/api/admin/sdr/notifications/route.ts` (new — polling endpoint)
- `apps/web/features/sdr/server/notifications.ts` (new)

---

### WP-601: "Assumir" Atomic Claim (Web)
**Owner**: WEB CRM WORKER
**Parallel**: Yes (with WP-600)
**Depends on**: WP-301

**Files**:
- `apps/web/app/admin/(dashboard)/leads/[id]/AssignLeadForm.tsx` — add "Assumir" atomic claim button
- `apps/web/features/lead/server/mutations.ts` — add `claimLeadAction` (atomic: only if `assignedToUserId = null`)

---

### WP-602: Júlia Summary Display (Web)
**Owner**: WEB CRM WORKER
**Parallel**: Yes (with WP-600, WP-601)
**Depends on**: WP-301

**Files**:
- `apps/web/app/admin/(dashboard)/leads/[id]/page.tsx` — add juliaSummary section
- `apps/web/app/admin/(dashboard)/leads/LeadsClient.tsx` — add temperature badge

---

## Wave 7 Work Packages

### WP-700: Golden Scenario Tests
**Owner**: QA WORKER
**Parallel**: No (requires Waves 0–6 complete)
**Depends on**: All prior waves

**Files**:
- `apps/sdr/tests/scenarios/` — Python test runner for all 10 YAML scenarios from `julia_sdr_master_pack/tests/conversation_scenarios/`
- `apps/sdr/tests/scenarios/runner.py`
- `apps/sdr/tests/scenarios/test_all_scenarios.py`

**Scenarios to implement**:
- purchase_actionable.yaml
- trade.yaml
- sale.yaml
- consignment.yaml
- refinancing.yaml
- financing_refusal.yaml
- explicit_vendor.yaml
- explicit_offer.yaml
- human_fromme.yaml
- inventory_missing_field.yaml

---

## Agent Role Assignments

| Role | Waves | Responsibilities |
|------|-------|-----------------|
| DATABASE WORKER | 0, 1 | Prisma schema, SQL migrations, Alembic setup, repository layer |
| SDR CORE WORKER | 0, 1, 3, 4 | Python scaffold, orchestrator, state merge, decision engine, handoff |
| AI / LLM WORKER | 1, 2, 3 | TurnFacts extraction, response composer, audio/image/document AI |
| EVOLUTION INTEGRATION WORKER | 2, 4 | Python Evolution client, media download, photo sending |
| WEB CRM WORKER | 0, 3, 6 | Webhook relay, document API, notifications, "Assumir", summary |
| QA WORKER | 7 | Golden scenarios, state tests, integration smoke tests |
| SECURITY WORKER | 9 | RLS, secrets audit, retention policy, go-live checklist |
