# CONVERSATION RUNTIME FINDINGS
> Hardening run — 2026-08-27
> Status: VERIFIED root causes (not hypotheses)

---

## Observed Smoke-Test Failure Sequence

| Turn | Customer | Júlia | Expected |
|------|----------|-------|----------|
| 1 | `Olá` | `Oi! Tudo bem por aí? Como posso te ajudar hoje?` | OK |
| 2 | ~15s audio | `Oi! Tudo bem por aí? Me conta, como posso ajudar você hoje?` | Should process audio and respond to content |
| 3 | `Gostaria de ver mais informações sobre uma Honda CG que vocês tem aí` | `Oi! Tudo bem? Sou a Júlia da FacilCar, como posso ajudar você hoje?` | Should search inventory |
| 4 | `Tranquilo Júlia, vocês vendem motos?` | `Oi! Tudo bem por aí? Como posso te ajudar hoje?` | Should respond semantically |

---

## VERIFIED ROOT CAUSES

### RC-1 · COMPOSER_CONTEXT_FAILURE — CRITICAL

**Location**: `apps/sdr/src/sdr/application/process_turn.py` lines 54–66

**Evidence**: The `state_map` passed to `compose_response` contains only 3 fields:
```python
state_map = {
    "language": merged.language,
    "thread_id": merged.thread_id,
    "missing_fields": [plan.ask_field] if plan.ask_field else [],
}
```

The LLM composer never receives:
- `intent` (commercial or not)
- `facts` (vehicle, budget, customer data extracted so far)
- `customer_name`
- `lifecycle_status`
- `should_introduce` (whether the assistant has already introduced itself)
- `assistant_turn_count` (how many bot turns have already occurred)
- Tool results (`tool_context=None` always)

**Effect**: The LLM has no business context to compose a relevant response. With no context, any action besides a hardcoded template falls back to a generic greeting or "how can I help you" pattern.

**Classification**: `COMPOSER_CONTEXT_FAILURE`

---

### RC-2 · RESPONSE_POLICY_FAILURE — Greeting Repeated Every Turn — CRITICAL

**Location**: `apps/sdr/src/sdr/understanding/response_composer.py` line 170–171

**Evidence**: The `SMALLTALK` action template unconditionally produces:
```python
if action == "smalltalk":
    return ["Oi! Sou a Júlia da FacilCar. Em que posso te ajudar hoje?"]
```

No `should_introduce` logic exists. No `assistant_turn_count` is tracked. Any turn that falls through to `SMALLTALK` — regardless of whether it's turn 1 or turn 10 — receives a full reintroduction greeting.

**Effect**: All commercial messages misclassified as `UNKNOWN` intent receive a greeting response, creating the observed loop.

**Classification**: `RESPONSE_POLICY_FAILURE` + `COMPOSER_CONTEXT_FAILURE`

---

### RC-3 · UNDERSTANDING_FAILURE — Commercial Language → SMALLTALK — CRITICAL

**Location**: `apps/sdr/src/sdr/understanding/extractor.py`

**Evidence**: When `OPENAI_API_KEY` is absent (or tests run), the heuristic fallback is used. For "Honda CG", "vocês vendem motos?", "gostaria de informações sobre..." the heuristic:

1. `_INTENT_PATTERNS` does not match any commercial pattern for these phrases
2. `_MODEL` list (line 62–66) does not include `CG`, `moto`, `scooter`, or most vehicle categories
3. Intent falls to `UNKNOWN`
4. Decision engine: `UNKNOWN` intent → `SMALLTALK` action → greeting

Even with OpenAI active, the LLM context is minimal:
```python
summary = f"intent={state.intent.value}; facts={list(state.facts.keys())}"
```
One line. No conversation history, no customer context, no prior turns.

**Classification**: `UNDERSTANDING_FAILURE` (heuristic path is `SEMANTIC_LANGUAGE_HEURISTIC`, masking as semantic understanding)

---

### RC-4 · TOOL_EXECUTION_FAILURE — Planned Tools Never Execute — CRITICAL

**Location**: `apps/sdr/src/sdr/application/process_turn.py` line 66

**Evidence**: The Decision Engine correctly plans `inventory_search` in some cases, but `tool_context` is ALWAYS `None`:
```python
bubbles = await compose_response(state_map, plan_map, tool_context=None)
```

`plan.tool_calls` is constructed by the Decision Engine (e.g., `[{"tool": "inventory_search"}]`) but is NEVER executed. The `ToolExecutor` does not exist in the current pipeline. `inventory.py` implements `search_published_vehicles` correctly but is never called during a turn.

**Effect**: For the `SHOW_OFFERS` action, the composer receives no inventory data and falls back to "Estou buscando opções no estoque publicado. Tem alguma preferência?" (generic no-data response).

**Classification**: `TOOL_EXECUTION_FAILURE`

---

### RC-5 · MEDIA_ENRICHMENT_FAILURE — Audio Path Disconnected — CRITICAL

**Location**: `apps/sdr/src/sdr/orchestrator.py` line 83

**Evidence**: Audio messages are stored via `ingest.ts` with `text=null`, `transcription=null`, `contentType="AUDIO"`. The orchestrator reads:
```python
text = row["text"] or row["transcription"] or ""
```
For audio, both are null → `text = ""`.

`process_media` and `transcribe_audio` exist and work correctly but are **never called in the orchestration pipeline**. The audio bytes are not stored in the DB and no download is attempted at processing time. `ingest.ts` stores no `mediaRef` data for the worker to use.

**Effect**: Audio messages become empty-text turns → `intent=UNKNOWN` → `SMALLTALK` → greeting.

**Classification**: `MEDIA_ENRICHMENT_FAILURE`

---

### RC-6 · STATE_NOT_PROPAGATED (NOT state loss) — VERIFIED

**Evidence**: Canonical state IS correctly persisted and loaded across turns:
- `canonical_state_to_json` serializes to DB `canonicalStateJson`
- `canonical_state_from_json` deserializes correctly
- `save_canonical_state` is called after every turn
- Worker reads `conv["canonicalStateJson"]` on every turn

**The state is NOT resetting.** The problem is that state is not propagated to the Composer. The composer never sees the accumulated state.

**Classification**: `STATE_NOT_PROPAGATED` (not `STATE_NOT_PERSISTED` or `STATE_NOT_LOADED`)

---

### RC-7 · DECISION_TRIGGER_INCOMPLETE — Inventory Search Not Triggered for Known Model

**Location**: `apps/sdr/src/sdr/domain/decision.py` lines 87–98

**Evidence**: Inventory search is only triggered when:
```python
state.intent in (PURCHASE, PURCHASE_FINANCING)
AND next_ask_field(state) == "desired_model"  # model is UNKNOWN
AND state.facts.get("budget")  # budget is known
```

For "Honda CG" scenario with LLM correctly extracting `desired_model=CG`:
- `next_ask_field` returns `"budget"` (model known, asking for budget)
- Condition fails → inventory search NOT triggered
- Customer asking to see vehicle → asked for budget instead

**Classification**: `DECISION_TRIGGER_INCOMPLETE`

---

## HEURISTIC AUDIT

| Heuristic | Classification | Status |
|-----------|---------------|--------|
| `@g.us` group JID detection in `jid-guard.ts` | `PROTOCOL_DETERMINISTIC` | ✅ Keep |
| `fromMe` → bot/human differentiation | `PROTOCOL_DETERMINISTIC` | ✅ Keep |
| `_HANDOFF_PATTERN` (explicit vendedor/humano request) | `SAFE_FAST_PATH` | ✅ Keep |
| `_OFFER_PATTERN` (dou/fecho/proposta) | `SAFE_FAST_PATH` | ✅ Keep |
| `_VISIT_PATTERN` (visitar/loja) | `SAFE_FAST_PATH` | ✅ Keep |
| `_HIGH_PURCHASE` (compro hoje/próximos dias) | `SAFE_FAST_PATH` | ✅ Keep |
| `_REFUSAL` (não quero mandar CPF) | `SAFE_FAST_PATH` | ✅ Keep |
| `_INTENT_PATTERNS` (refinanciar, consignar, etc.) | `SAFE_FAST_PATH` | ✅ Keep (finite actions) |
| `_MODEL` finite list (hilux, onix, hb20...) | `SEMANTIC_LANGUAGE_HEURISTIC` | ⚠️ Reduce scope — NOT allowed to shadow LLM |
| `_ES_HINTS` finite word list (hola, quiero...) | `SEMANTIC_LANGUAGE_HEURISTIC` | ⚠️ Marginally useful — keep but don't expand |
| Greeting check (low == "oi", "olá"...) | `SEMANTIC_LANGUAGE_HEURISTIC` | ⚠️ Only for pure greetings; should not catch commercial lang |

**Critical finding**: The heuristic fallback is currently used when `OPENAI_API_KEY` is absent. In production with the key present, the LLM path runs. But the LLM receives minimal context (1-line summary) and insufficient context to compose a relevant response.

---

## STATE PERSISTENCE VERIFICATION

| Question | Answer | Evidence |
|----------|--------|----------|
| Same Conversation/thread reused? | ✅ Yes | `ingest.ts` upserts by `instanceName_phone` |
| Previous canonical state persisted? | ✅ Yes | `save_canonical_state` writes `canonicalStateJson` |
| Previous canonical state loaded on next turn? | ✅ Yes | `canonical_state_from_json` reads `conv["canonicalStateJson"]` |
| Prior Message rows present? | ✅ Yes | `list_pending_messages` joins Message to Conversation |
| Accumulated summary persisted? | ⚠️ Column exists (`accumulatedSummary`) but never written | Not filled by current implementation |
| Deterministic merge preserving prior facts? | ✅ Yes | `deterministic_merge` is correct — omission never deletes |
| State correct but not reaching Composer? | ✅ YES — this is the actual failure | RC-1 above |

---

## PIPELINE STAGE ANALYSIS

```
Provider Event  → ✅ Received by Vercel webhook, stored in DB
InboundTurn     → ⚠️ No canonical InboundTurn type; text/audio diverge
Media Enrichment → ❌ RC-5: Audio never transcribed
ConversationContextBuilder → ❌ Missing; understanding gets 1-line summary
Understanding Engine → ⚠️ RC-3: Heuristic for OPENAI_API_KEY=absent; LLM gets minimal context
TurnFacts       → ✅ Correctly structured, correct schema
Deterministic Merge → ✅ Correct — omission safe, critical fields protected
Decision Engine → ✅ Mostly correct; RC-7: inventory trigger incomplete
ActionPlan      → ✅ Correctly constructed
Tool Executor   → ❌ RC-4: MISSING — tools never executed
ToolResults     → ❌ Never populated (tool executor missing)
ResponseDirective → ❌ Missing — state_map has 3 fields
Response Composer → ⚠️ RC-1+RC-2: Insufficient context, greeting loop
Response Validator → ✅ Exists and works
Provider        → ✅ sendText → Evolution works correctly
```

---

## BUGS THAT ARE NOT PRESENT (verified)

- State reset across turns: NOT occurring (state persists correctly)
- Duplicate conversation creation: NOT occurring (upsert by instanceName+phone)
- Evolution send failures: NOT occurring (sendText returns success)
- Lock/debounce issues: NOT occurring (Redis lock path works)
- fromMe greeting loop: NOT occurring (bot outbound pre-registered)

---

## REQUIRED ARCHITECTURAL CORRECTIONS

1. **Composer Context Contract**: Pass full `ResponseDirective` with intent, facts, customer, lifecycle, should_introduce, tool_results
2. **Introduction Policy**: Track `assistant_turn_count` in canonical state; derive `should_introduce` deterministically
3. **Tool Executor**: Implement `execute_tool_calls` in the `process_turn` pipeline
4. **Audio Enrichment**: Wire `transcribe_audio` into orchestration; store mediaRef in ingest for worker use
5. **Conversation Context Builder**: Pass richer state summary to LLM understanding
6. **Inventory Trigger**: Add case for known model + commercial intent
7. **Runtime Trace**: Add `SDR_TRACE` boundary tracer
8. **Replay Harness**: Add `python -m sdr.replay <fixture>`
