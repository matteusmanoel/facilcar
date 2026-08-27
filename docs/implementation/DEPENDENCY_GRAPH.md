# DEPENDENCY_GRAPH — Wave and Work Package Dependencies

## Wave Dependencies (Sequential Gates)

```
WP-000 (DB Migrations)    ──┐
WP-001 (Python Scaffold)  ──┤─► [WAVE 0 GATE] ──► WP-100 (Domain Types)
WP-002 (Webhook Relay)    ──┘                          │
                                                        ▼
                                WP-101 (Understanding)─┐
                                WP-102 (Decision)      ├─► WP-103 (Orchestrator) ─► [WAVE 1 GATE]
                                WP-104 (Lead/Customer) ─┘                              │
                                                                                        ▼
                                WP-200 (Evolution Client)─┐                       [WAVE 2 GATE]
                                WP-201 (Media Processor)  ─┘                           │
                                                                                        ▼
                                WP-300 (Doc Extractor)  ──┐                      [WAVE 3 GATE]
                                WP-301 (Handoff Pipeline) ──┤                          │
                                WP-302 (Doc Storage Web)  ──┘                          ▼
                                                                                  [WAVE 4 GATE]
                                WP-400 (Inventory Tool) ──┐                            │
                                WP-401 (Photo Tool)     ──┘                            ▼
                                                                                  [WAVE 5 GATE]
                                                          (All 6 business flows)       │
                                                                                        ▼
                                WP-600 (Notifications)  ──┐                      [WAVE 6 GATE]
                                WP-601 (Assumir Claim)  ──┤                            │
                                WP-602 (Summary Display) ──┘                           ▼
                                                                                  [WAVE 7 GATE]
                                WP-700 (Golden Scenarios) (QA)                         │
                                                                                        ▼
                                                                                  [WAVE 8: Staging]
                                                                                        │
                                                                                        ▼
                                                                                  [WAVE 9: Prod]
```

## Parallel Opportunities Per Wave

### Wave 0 — All 3 WPs can run in parallel
- WP-000: DATABASE WORKER creates schema/migrations
- WP-001: SDR CORE WORKER creates Python scaffold
- WP-002: WEB CRM WORKER creates webhook relay

### Wave 1 — WP-100 first, then 101/102/104 parallel, then WP-103
- WP-100 must complete first (defines types)
- WP-101 + WP-102 + WP-104 can run in parallel
- WP-103 waits for WP-101 + WP-102

### Wave 2 — WP-200 and WP-201 can run in parallel
- Both depend on WP-001 only

### Wave 3 — WP-300 and WP-302 can run in parallel; WP-301 waits for WP-300
- WP-300: AI / LLM WORKER
- WP-302: WEB CRM WORKER (independent)
- WP-301: waits for WP-300

### Wave 4 — WP-400 and WP-401 fully parallel
- Different owners, no shared files

### Wave 6 — WP-600, WP-601, WP-602 fully parallel
- Different files in web app, different owners

---

## Critical Path

```
WP-000 → WP-100 → WP-102 → WP-103 → WP-301 → Wave 7 → Wave 8 → Wave 9
```

The critical path is: schema → domain types → decision engine → orchestrator → handoff → QA → staging → production.

The LLM components (WP-101, WP-201, WP-300) run in parallel to the critical path and don't block it until Wave 3.

---

## Key Integration Points (Cross-Role Dependencies)

| Dependency | From Role | To Role | Artifact |
|-----------|-----------|---------|---------|
| DB schema | DATABASE WORKER | All | Prisma generated types |
| `TurnFacts` type | SDR CORE WORKER | AI / LLM WORKER | `domain/types.py` |
| `Action` enum | SDR CORE WORKER | AI / LLM WORKER | `domain/types.py` |
| `EvolutionClient.send_text()` | EVOLUTION WORKER | SDR CORE WORKER | `infrastructure/evolution_client.py` |
| `extract_turn_facts()` | AI / LLM WORKER | SDR CORE WORKER | `understanding/extractor.py` |
| `compose_response()` | AI / LLM WORKER | SDR CORE WORKER | `understanding/response_composer.py` |
| Webhook creates Message rows | WEB CRM WORKER | SDR CORE WORKER | Message DB table |
| `SdrNotification` rows | DATABASE WORKER | WEB CRM WORKER | notification_repository.py |
