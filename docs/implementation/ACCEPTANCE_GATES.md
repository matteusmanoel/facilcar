# ACCEPTANCE_GATES — Wave Completion Criteria

> Each gate must pass before the next wave starts.
> Gates are verified by running the specified commands.

---

## Wave 0 Gate

**All must pass before Wave 1 starts.**

```bash
# G0-1: Migrations applied
cd apps/web && npx prisma migrate status
# Expected: All migrations applied, no pending

# G0-2: New tables exist
psql $DATABASE_URL -c "\dt facilcar.*" | grep -E "Conversation|Message"
# Expected: Both tables present

# G0-3: Python service starts
curl http://localhost:8000/health
# Expected: {"ok": true}

# G0-4: Webhook receives message
curl -X POST http://localhost:3000/api/webhooks/sdr \
  -H "x-sdr-secret: $SDR_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"event":"MESSAGES_UPSERT","instance":"facilcar-sdr","data":{"key":{"remoteJid":"5545988432998@s.whatsapp.net","fromMe":false,"id":"TEST001"},"message":{"conversation":"Oi"}}}'
# Expected: {"ok": true, "conversationId": "...", "messageId": "..."}

# G0-5: Group blocked
curl -X POST http://localhost:3000/api/webhooks/sdr \
  -H "x-sdr-secret: $SDR_WEBHOOK_SECRET" \
  -d '{"data":{"key":{"remoteJid":"120363000000@g.us","fromMe":false,"id":"GROUP001"},"message":{"conversation":"oi"}}}'
# Expected: {"ok": true, "handled": 0, "reason": "group_ignored"}

# G0-6: JULIA_ENABLED kill switch
JULIA_ENABLED=false && [test that webhook still stores messages but sends no reply]
```

---

## Wave 1 Gate

**Text-only conversation from greeting to QUALIFIED lead.**

```bash
# G1-1: State merge invariants
cd apps/sdr && python -m pytest tests/unit/test_merge.py -v
# Expected: All pass, including unknown!=false and omission safety

# G1-2: Decision engine
python -m pytest tests/unit/test_decision.py -v
# Expected: All pass

# G1-3: Purchase flow integration test
python -m pytest tests/integration/test_purchase_flow.py -v
# Expected: Conversation goes BOT_ACTIVE → QUALIFYING → READY_FOR_HANDOFF
#           Lead created with type=VEHICLE_INTEREST or FINANCING, status=QUALIFIED
#           juliaSummary set

# G1-4: Greeting does NOT create lead
# Verify: after "oi", Lead count = 0, Conversation exists

# G1-5: Response in Portuguese
# Verify: response contains pt-BR text, 1–3 bubbles, no invented prices
```

---

## Wave 2 Gate

**Multimodal ingestion working.**

```bash
# G2-1: Audio transcription
python -m pytest tests/unit/test_media_processor.py::test_audio_transcription -v
# Expected: Returns text string, no exception

# G2-2: Image description (no fabrication)
python -m pytest tests/unit/test_media_processor.py::test_image_no_mechanical_claims -v
# Expected: Description does NOT contain price/km/sinistro/garantia statements

# G2-3: Group messages ZERO rows
# Send group message, verify Conversation count unchanged

# G2-4: fromMe human → HUMAN_ACTIVE
# Send fromMe=true with unknown messageId, verify conversation.botStatus=HUMAN_ACTIVE
# Verify: no bot reply sent after HUMAN_ACTIVE
```

---

## Wave 3 Gate

**Document flow and handoff pipeline.**

```bash
# G3-1: Document extraction
python -m pytest tests/unit/test_document_extractor.py -v
# Expected: CNH extraction returns name/CPF/birthDate (or null for each)

# G3-2: Conflict detection
python -m pytest tests/unit/test_document_extractor.py::test_conflict_asks_confirmation -v
# Expected: When text CPF ≠ document CPF, action=ask_confirmation (not silent overwrite)

# G3-3: Private bucket access
# Verify: LEAD_MANAGER role → 403 on signed URL endpoint
# Verify: ADMIN role → 200 with time-limited URL

# G3-4: Handoff irreversibility
python -m pytest tests/unit/test_handoff.py::test_handoff_irreversible -v
# Expected: After HUMAN_ACTIVE, no bot message sent for subsequent inbound messages

# G3-5: One confirmation message
python -m pytest tests/unit/test_handoff.py::test_one_confirmation_only -v
# Expected: Exactly one message sent at handoff, none after

# G3-6: Lead qualified
# Verify: Lead.status = QUALIFIED, Lead.juliaSummary populated, Lead.assignedToUserId = null
```

---

## Wave 4 Gate

**Inventory tools working.**

```bash
# G4-1: PUBLISHED-only filter
python -m pytest tests/unit/test_inventory_tool.py::test_published_only -v
# Expected: DRAFT/RESERVED/SOLD vehicles never returned

# G4-2: No fabrication
python -m pytest tests/unit/test_inventory_tool.py::test_missing_field_returns_unknown -v
# Expected: Missing mileage → "não consta no anúncio", not invented value

# G4-3: ≤3 alternatives
python -m pytest tests/unit/test_inventory_tool.py::test_max_3_alternatives -v

# G4-4: Ranking: price → category → brand
python -m pytest tests/unit/test_inventory_tool.py::test_alternative_ranking -v
```

---

## Wave 5 Gate

**All 6 business flows produce QUALIFIED leads with correct types.**

```bash
cd apps/sdr && python -m pytest tests/integration/test_all_flows.py -v
```

| Flow | Expected LeadType | Expected FinancingRequest | Expected SellRequest |
|------|------------------|--------------------------|---------------------|
| Purchase | VEHICLE_INTEREST | No | No |
| Financing | FINANCING | Yes | No |
| Trade-in | TRADE_IN | No | Yes (trade vehicle) |
| Sale | SELL_VEHICLE | No | Yes |
| Consignment | CONSIGNMENT | No | Yes |
| Refinancing | REFINANCING | Yes | No |

Each must reach `Lead.status = QUALIFIED` with `juliaSummary` populated.

---

## Wave 6 Gate

**Web CRM enhancements working.**

```bash
# G6-1: New lead notification visible (manual check or E2E test)
# Verify: After QUALIFIED lead created, /admin/leads shows badge

# G6-2: Atomic claim
# ADMIN A calls claimLeadAction(leadId)
# ADMIN B simultaneously calls claimLeadAction(leadId)
# Exactly one gets it (atomic update WHERE assignedToUserId IS NULL)

# G6-3: juliaSummary in lead detail
# Navigate to /admin/leads/{id}, verify juliaSummary section visible

# G6-4: Temperature badge in Kanban
# Verify: HOT/WARM/COLD badge visible on Kanban card
```

---

## Wave 7 Gate

**All golden scenarios pass.**

```bash
cd apps/sdr && python -m pytest tests/scenarios/ -v
```

All 10 scenarios from `julia_sdr_master_pack/tests/conversation_scenarios/` must pass:
- purchase_actionable
- trade
- sale
- consignment
- refinancing
- financing_refusal
- explicit_vendor
- explicit_offer
- human_fromme
- inventory_missing_field

```bash
# Full test suite
python -m pytest tests/ -v --tb=short
# Expected: 0 failures
```

---

## Wave 8 Gate (Staging)

**Full E2E on staging environment using dev WhatsApp number `5545988432998`.**

Manual verification + automated smoke tests:
- [ ] Send message on dev WhatsApp → received in Evolution → Júlia replies within 5s
- [ ] Complete purchase flow → QUALIFIED lead in staging admin
- [ ] Complete financing flow → QUALIFIED lead with FinancingRequest
- [ ] Send CNH photo → document stored, fields extracted
- [ ] Admin on staging can see QUALIFIED leads with juliaSummary
- [ ] "Assumir" button works (seller claims lead)
- [ ] `JULIA_ENABLED=false` → messages stored, no replies

---

## Wave 9 Gate (Production)

- [ ] RLS enabled on Customer, Lead, FinancingRequest, User, SdrDocument
- [ ] All secrets rotated from defaults
- [ ] Commercial playbook validated by Milton/Eraldo
- [ ] TLS on VPS verified
- [ ] Backup strategy documented
- [ ] Rollback procedure tested
- [ ] `JULIA_ENABLED=true` confirms pilot on 100% of new conversations
