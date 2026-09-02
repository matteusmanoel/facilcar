# IMPLEMENTATION PLAN — Júlia SDR Multi-Agent Run

> Based on: `docs/preflight/PREFLIGHT_REPORT.md`
> Status: READY_WITH_NON_BLOCKING_GAPS
> Implementation start: Wave 0

## Guiding Principles

1. One wave at a time. Each wave has a hard acceptance gate.
2. Agents own specific files. No two agents touch the same file.
3. LLM interprets; deterministic code governs state.
4. All DB migrations are additive. No existing table/enum modified without `IF NOT EXISTS`.
5. Tests validate public behavior, not implementation details.
6. Cost priority: fast paths first, LLM as late as possible per turn.

---

## Wave Map

```
WAVE 0  ─── Foundations: Python scaffold, DB migrations, webhook relay, env config
    ↓ GATE: migrations applied, webhook receives messages, Conversation/Message rows created
WAVE 1  ─── Core conversation engine: orchestrator, state merge, decision engine, LLM pipeline
    ↓ GATE: text-only conversation completes purchase intent → Lead created → QUALIFIED
WAVE 2  ─── Evolution adapter: multimodal, audio transcription, image understanding, groups blocked
    ↓ GATE: audio turns transcribed, image described, document received and stored
WAVE 3  ─── Document flow + handoff: CNH/CRLV extraction, private bucket, Lead qualified, seller notified
    ↓ GATE: handoff creates QUALIFIED lead, summary generated, Júlia silences
WAVE 4  ─── Inventory tools + vehicle photos
    ↓ GATE: vehicle search returns correct PUBLISHED results, photos sent to user
WAVE 5  ─── Financing / sell / trade / consignment / refinancing flows
    ↓ GATE: all 6 business flows produce QUALIFIED lead with correct type and data
WAVE 6  ─── Web CRM enhancements: notifications, "Assumir", Júlia summary, temperature
    ↓ GATE: seller sees new lead notification, can claim atomically, sees Júlia summary
WAVE 7  ─── Conversation QA + regression: golden scenarios, state invariants, no-repeat, conflict
    ↓ GATE: all 10 conversation scenarios pass; state tests pass; no regression
WAVE 8  ─── Staging integration: deploy, seed, E2E, smoke tests
    ↓ GATE: full E2E on staging for all 6 flows
WAVE 9  ─── Production readiness: security, RLS, rollback, commercial go-live gate
```

---

## Wave 0: Foundations

**Objective**: Create the Python SDR service scaffold, apply DB migrations, and establish the webhook relay.

**Acceptance gate**:
- [ ] `apps/sdr/` directory with working FastAPI skeleton
- [ ] `Conversation` and `Message` tables in DB (migration applied)
- [ ] Webhook at `/api/webhooks/sdr/route.ts` receives Evolution payloads, creates Conversation + Message rows
- [ ] Group messages blocked at ingress (`@g.us`)
- [ ] `fromMe=true` from unknown sender marks conversation HUMAN_ACTIVE
- [ ] `JULIA_ENABLED=true/false` feature flag operational
- [ ] `docker-compose.sdr.yml` brings up services

**Files created (Wave 0 only)**:
See `WORK_PACKAGES.md` → WP-000, WP-001, WP-002

---

## Wave 1: Core Conversation Engine

**Objective**: Text-only conversation pipeline from ingestion to QUALIFIED lead.

**Acceptance gate**:
- [ ] State merge: omission does not delete prior state
- [ ] Unknown != false test passes
- [ ] Intent classification from text works for all 6 business types
- [ ] Decision engine produces correct actions deterministically
- [ ] LLM response in pt-BR, 1–3 bubbles, no invented facts
- [ ] Purchase intent flow: BOT_ACTIVE → QUALIFYING → READY_FOR_HANDOFF → QUALIFIED
- [ ] Lead created only after commercial intent detected (not on greeting)
- [ ] `juliaSummary` populated on handoff

---

## Wave 2: Evolution Adapter + Multimodal

**Objective**: Audio, image, document ingestion. Robust message normalization.

**Acceptance gate**:
- [ ] Audio message → Whisper transcription → processed as text
- [ ] Image message → described with Vision (no fabricated mechanical/value claims)
- [ ] Document/PDF → stored in private bucket
- [ ] Group messages: 100% blocked, zero state created
- [ ] `fromMe=true` human detection: no bot/human collision

---

## Wave 3: Document Flow + Handoff

**Objective**: Document extraction, private storage, handoff pipeline, seller notification.

**Acceptance gate**:
- [ ] CNH/CRLV image → extract CPF, name, birth_date (or null for each)
- [ ] Extracted fields upserted into `FinancingRequest` (CPF, birthDate)
- [ ] Original stored in `sdr-documents` private bucket
- [ ] LEAD_MANAGER cannot retrieve signed URL (403)
- [ ] ADMIN can retrieve signed URL (200, expires in 15 min)
- [ ] Conflict detection: text says year X, document says year Y → asks for confirmation
- [ ] `Lead.status = QUALIFIED` set exactly once per handoff
- [ ] `Message.isHumanSent` correctly distinguishes bot vs seller messages

---

## Wave 4: Inventory Tools + Photos

**Objective**: Vehicle search, photo sending, alternative suggestions.

**Acceptance gate**:
- [ ] Vehicle search queries only `status=PUBLISHED`
- [ ] Returns up to 3 alternatives when exact match not found (price→category→brand priority)
- [ ] Missing fields (mileage, color) never fabricated — returns "não consta no anúncio"
- [ ] Photos sent via Evolution `sendMedia`
- [ ] `aceitaTroca`, `aceitaSemEntrada` fields used only when non-zero/non-false

---

## Wave 5: All Business Flows

**Objective**: Complete the 6 business flow implementations with correct data collection.

**Flows**:
1. Purchase (compra)
2. Purchase + financing (compra com financiamento)
3. Trade-in (troca)
4. Sale (venda)
5. Consignment (consignação)
6. Refinancing (refinanciamento)

**Acceptance gate**:
- [ ] Each flow reaches QUALIFIED with correct `LeadType`
- [ ] `FinancingRequest` populated for flows 2 and 6
- [ ] `SellRequest` populated for flows 3, 4, 5
- [ ] No mandatory field blocks handoff when lead is otherwise actionable
- [ ] CPF/renda refusal does not destroy lead
- [ ] Installment count is nice-to-have only (never blocks)

---

## Wave 6: Web CRM Enhancements

**Objective**: Notification center, "Assumir" atomic claim, Júlia summary, temperature indicator.

**Acceptance gate**:
- [ ] Admin sees badge/indicator for new QUALIFIED leads
- [ ] "Assumir" button sets `assignedToUserId` atomically (first seller wins)
- [ ] `Lead.juliaSummary` displayed in lead detail page
- [ ] `Lead.temperature` (HOT/WARM/COLD) displayed in Kanban card
- [ ] No second "Assumir" allowed if already assigned
- [ ] New lead notification visible without page refresh (polling OR realtime)

---

## Wave 7: QA + Regression

**Objective**: Complete test coverage for all critical behaviors.

**Test categories**:
- State merge unit tests (unknown != false, omission safety, conflict detection)
- JID normalization tests (group, LID, device suffix, Brazilian 9-digit)
- Handoff lifecycle tests (irreversibility, one confirmation message, silence after)
- Inventory availability tests (PUBLISHED only, no fabrication)
- Document conflict tests (text vs document field mismatch)
- No-repeat-known-data tests (known CPF not re-requested)
- fromMe human collision tests
- Golden scenario tests (all 10 conversation_scenarios from julia_sdr_master_pack)
- Integration smoke tests (Evolution → DB → Lead created)
- E2E: one complete flow per business type

---

## Wave 8: Staging Integration

**Blocked by**: HITL-001 (staging project), HITL-003 (webhook routing)

**Tasks**:
- Provision/confirm staging Supabase project
- Apply all migrations to staging
- Seed with catalog snapshot (vehicles + SiteSettings, no PII)
- Configure staging Evolution instance with dev number `5545988432998`
- Run E2E tests against staging
- Validate all 6 business flows on staging WhatsApp

---

## Wave 9: Production Readiness

**Blocked by**: HITL-002 (commercial playbook validation)

**Tasks**:
- Enable RLS on PII tables (Customer, Lead, FinancingRequest, User, SdrDocument)
- Provision Hostinger VPS
- Deploy Docker Compose stack
- Set up TLS (Let's Encrypt)
- Rotate all secrets
- Validate commercial playbook with Milton/Eraldo
- Implement 180-day retention cleanup job
- Final security review
- Go-live gate: commercial validation

---

## File Ownership Registry

See `FILE_OWNERSHIP.md` for detailed per-file agent assignments.

## Work Packages

See `WORK_PACKAGES.md` for detailed WP breakdown.

## Dependency Graph

See `DEPENDENCY_GRAPH.md`.

## Acceptance Gates

See `ACCEPTANCE_GATES.md`.

## Rollback Plan

See `ROLLBACK_PLAN.md`.
