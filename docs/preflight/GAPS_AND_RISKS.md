# GAPS_AND_RISKS — Pre-Flight Findings

## Gaps (Missing Capabilities)

### G-001: No Conversation / Thread Table
**Status**: CRITICAL — blocks Wave 0
No table to track WhatsApp thread state (bot/human, language, handoff state, last_message_at, active lead IDs). Must be created as an additive migration.

### G-002: No Message Table
**Status**: CRITICAL — blocks Wave 0
No persistent message log. Required for: deduplication, state reconstruction, context building, audit trail. Must be created as an additive migration.

### G-003: No VisitInterest Table
**Status**: Required — blocks Wave 2
`docs/19_SOURCE_OF_TRUTH.md` confirms absence. Simple table: leadId, dateHint, period, notes, createdAt.

### G-004: No Private Document Bucket
**Status**: Required — blocks Wave 3
Only `vehicle-images` (public) bucket exists. Need `sdr-documents` private bucket for CNH, CRLV, income/residence proofs.

### G-005: No SdrDocument Table
**Status**: Required — blocks Wave 3
No metadata table for uploaded documents (type, storageKey, extractedJson, processingStatus, retentionPolicy).

### G-006: No Notification Infrastructure
**Status**: Required — blocks Wave 4
No Supabase Realtime, no WebSocket, no SSE, no notification center in web app. Options:
- Server-Sent Events (lightweight, unidirectional, works with Next.js)
- Supabase Realtime (already available, zero infra)
- Polling fallback (simplest, less real-time)

### G-007: Julia Fields in Vehicle Not Filled
**Status**: Non-blocking for launch, affects SDR quality
`aceitaTroca`, `aceitaSemEntrada`, `parcelaBase`, `entradaMinima`, `rendaMinimaSugerida` all zero in production. SDR must not use these as policy anchors. Requires Milton/Eraldo to populate per vehicle.

### G-008: No Commercial Knowledge Base
**Status**: Product blocker (not implementation blocker)
No FAQ, no financing policy, no consignment rules, no playbook in database. SDR will use: SiteSettings (address), Vehicle catalog (stock/price), and deterministic domain rules from code. For naturalistic responses, a short validated knowledge document (plain text, ≤4KB) will need to be injected into the system prompt.

### G-009: No LEAD_MANAGER User in Production
**Status**: Low risk for launch
Milton Barrios is ADMIN — he can access leads. No seller with LEAD_MANAGER role exists. The "Assumir" (claim) flow should work with ADMIN role too. Create at least one LEAD_MANAGER before go-live for proper seller workflow.

### G-010: RLS Disabled on All Tables
**Status**: Security gap — requires mitigation before go-live
All 16 `facilcar` tables have `rowsecurity=false`. The app uses Prisma server-side, which is safe IF Supabase Data API (REST/GraphQL) is not enabled for anonymous access. Must verify and add RLS before production launch. Not blocking for development.

### G-011: No n8n Workflow JSON
**Status**: Non-blocking
The historic n8n workflow for Júlia was referenced in discovery but is NOT in this repository. Regression test scenarios exist in `julia_sdr_master_pack/tests/conversation_scenarios/`. These are sufficient as behavioral specs.

### G-012: No Real Conversation Corpus
**Status**: Product quality risk
Zero real customer conversations in the system. Test scenarios are synthetic. SDR quality will need validation with real conversations before go-live (D-019/commercial go-live gate).

### G-013: `munnfnfudrsoblwgivjn` Supabase Project Status Unknown
**Status**: HITL required (see HITL_REQUIRED.md)
Root-level `supabase/.temp` points to this project. Either staging or orphan. If staging: great, reuse it. If orphan: create new. Does not block implementation.

---

## Risks

### R-001: Dual Lockfile (npm + pnpm)
**Severity**: Medium
`package-lock.json` and `pnpm-lock.yaml` coexist at root. If a developer runs `pnpm install` expecting workspace behavior, they get an empty install. Recommendation: remove `pnpm-lock.yaml`.

### R-002: LeadStatus Mismatch Between SDR Docs and Schema
**Severity**: Low (RESOLVED)
SDR docs say `NEW → QUALIFIED → WON/LOST`. Schema has additional states: `IN_PROGRESS`, `CONTACTED`, `SPAM`. These are human-managed states that do not conflict with SDR lifecycle. SDR uses NEW (creation) and QUALIFIED (handoff). Resolution: confirmed non-issue.

### R-003: Vehicle Data Gaps
**Severity**: Medium
24/41 vehicles missing mileage, 38/41 missing color. SDR must handle "não consta / confirme na loja" responses gracefully. Decision Engine must not fabricate missing fields.

### R-004: RLS Off + service_role Exposure
**Severity**: High (pre-production)
If the Supabase URL + service_role key were ever leaked to a browser or public endpoint, all data in `facilcar` schema would be exposed. Verify: (a) service_role is server-only, (b) Supabase Data API is restricted/disabled for this schema, (c) no client-side Supabase calls use service_role.

### R-005: fromMe Human Detection Reliability
**Severity**: Medium
Detecting whether a `fromMe=true` message is from a human vs the SDR itself requires tracking all SDR-generated message IDs. Race condition: if the SDR crashes between sending and recording the ID, a bot message could be misidentified as human. Mitigation: record the sent message ID in Redis BEFORE sending, and confirm after.

### R-006: Evolution QR/Session Stability
**Severity**: Medium
Companion fingerprint is Chrome/Chrome (correct per docker-compose comment). WhatsApp Web sessions can disconnect due to phone restarts, WhatsApp updates, or rate limits. SDR must handle Evolution disconnection gracefully: queue incoming messages, alert admin, do not lose state.

### R-007: Knowledge Base Void (Commercial Content)
**Severity**: High for quality, medium for launch
Without a validated commercial playbook (financing conditions, consignment terms, trade-in evaluation rules), the SDR will make generic statements. The LLM will respond based on generic automotive knowledge, not FacilCar-specific rules. This is a product quality risk that must be addressed before pilot launch, not a coding blocker.

### R-008: No CI/CD for Python Service
**Severity**: Medium
No CI pipeline exists. Tests must be run manually. For MVP, a simple `Makefile` + `pytest` is sufficient. Before production: add basic CI (GitHub Actions or equivalent).

### R-009: Staging Project Unknown
**Severity**: Low
If `munnfnfudrsoblwgivjn` turns out to be an orphan or inaccessible, a new Supabase project must be created for staging. 15-minute task but needs decision.

### R-010: Cost Overrun if Conversation Volume Spikes
**Severity**: Low-medium
R$500/month budget is comfortable for dozens of simultaneous conversations. If volume reaches hundreds/day, costs may approach the limit. Mitigation: fast paths without LLM where possible, intent caching, hard limits on LLM calls per conversation.

---

## Conflicts Found

| ID | Description | Status |
|----|-------------|--------|
| C-001 | `pnpm-lock.yaml` (empty) vs `package-lock.json` | `NON_BLOCKING_TECHNICAL_DECISION` — remove pnpm-lock |
| C-002 | Two Supabase project refs in `.temp` | `HITL_REQUIRED` — see HITL_REQUIRED.md |
| C-003 | LeadStatus has extra states not in SDR docs | `RESOLVED_FROM_EVIDENCE` — extra states are human-managed, SDR only uses NEW/QUALIFIED |
| C-004 | `HANDOFF.md` says "no migrations/ folder, use db:push" | `RESOLVED_FROM_EVIDENCE` — migrations/ folder exists and is used; HANDOFF.md is outdated |
| C-005 | Vehicle Julia fields exist but are empty | `NON_BLOCKING_TECHNICAL_DECISION` — SDR treats as unavailable until filled |
| C-006 | SiteSettings.defaultWhatsappNumber vs SDR dev number | `RESOLVED_FROM_EVIDENCE` — production 5545999974232, dev 5545988432998; separate Evolution instances |
