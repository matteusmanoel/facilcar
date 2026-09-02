# OPENAI_SURFACE — Minimal API Surface for MVP

> Decision D-004: OpenAI permitted including for sensitive documents.
> Package: `openai` v7.4.0 already in `apps/web`. Python SDK needed for `apps/sdr`.

## API Calls Required (in priority order)

### 1. Understanding / TurnFacts Extraction
**API**: `chat.completions.create` with `response_format: { type: "json_schema" }`
**Model recommendation**: `gpt-4.1-mini` or `gpt-4o-mini` (low cost, structured output)
**Input**: System prompt (role + rules) + accumulated conversation summary + recent N turns (not full history) + user message
**Output**: TurnFacts JSON (intent, language, facts{}, signals{}, confidence{})
**Calling frequency**: Once per inbound message turn (after debounce)
**Cost driver**: Context length. Keep to <2000 tokens by using rolling summary instead of full history.

### 2. Response Composition
**API**: `chat.completions.create`
**Model recommendation**: `gpt-4.1-mini` for most turns; fallback to `gpt-4o` only for edge cases
**Input**: Role prompt (Júlia persona) + conversation state summary + current intent + approved action + inventory results if any
**Output**: 1–3 short WhatsApp message bubbles in pt-BR or Spanish
**Calling frequency**: Once per turn (after Decision Engine produces approved action)
**Cost driver**: Response tokens. Keep responses short (1–3 bubbles × ~100 tokens each).

### 3. Audio Transcription
**API**: `audio.transcriptions.create` (Whisper)
**Model**: `whisper-1`
**Input**: Audio file (m4a, ogg, mp3 — as downloaded from Evolution)
**Output**: Plain text
**Calling frequency**: Only when `audioMessage` received
**Cost**: $0.006/min — low for typical voice notes (<30 seconds)

### 4. Document / Image Extraction
**API**: `chat.completions.create` with vision (image_url)
**Model**: `gpt-4o` or `gpt-4.1` (Vision capable)
**Input**: Base64 image of CNH/CRLV/document + schema extraction prompt
**Output**: Structured JSON (name, CPF, birth_date, license_number, plate, etc.)
**Calling frequency**: Only when document/image received AND context is a data-collection step
**Cost driver**: Highest per-call cost. Minimize by only calling when intent is financing/document-collection.

### 5. General Image Understanding (vehicle photos)
**API**: `chat.completions.create` with vision
**Model**: `gpt-4o-mini` (sufficient for basic description)
**Input**: Vehicle photo from customer (trade-in, sell)
**Output**: Brief description of what is visible (make/model guess, visible damage, general condition)
**Constraint**: NEVER conclude mechanical state, accident history, or market value from photos.
**Calling frequency**: Only when customer sends photo in trade-in/sell/consignment context

### 6. Embeddings (RAG — conditional)
**API**: `embeddings.create`
**Model**: `text-embedding-3-small`
**Decision**: **NOT in MVP unless knowledge base is created.** Currently no knowledge base exists in the database. The business rules are encoded deterministically. Add RAG only if:
- A curated, validated knowledge document (financing policy, trade-in rules, etc.) is created
- AND the document is too large for a context-window injection
**pgvector**: NOT installed in production — additional setup required if RAG is adopted.

---

## NOT Required for MVP

- Fine-tuned models (use prompting + structured output)
- Assistants API / Threads API (unnecessary overhead)
- Batch API (latency requirement conflicts with real-time conversation)
- Moderation API (not required per security doc)
- Full document parsing API (Vision is sufficient)

---

## Cost Estimation

| Call Type | Frequency | Est. Tokens/Call | Model | Cost/Call est. |
|-----------|-----------|-----------------|-------|---------------|
| TurnFacts | ~every message | ~1500 in / 300 out | gpt-4.1-mini | ~$0.0005 |
| Response | ~every turn | ~1000 in / 200 out | gpt-4.1-mini | ~$0.0003 |
| Audio | ~10% of messages | ~30s audio | whisper-1 | ~$0.003 |
| Document extract | ~5% of messages | image | gpt-4o | ~$0.01–0.03 |

**Estimate for MVP volume** (assume 500 conversations/month, ~10 turns each):
- ~5,000 TurnFacts calls: ~$2.50
- ~5,000 Response calls: ~$1.50
- ~500 audio calls: ~$1.50
- ~250 document calls: ~$5.00
- **Total AI ≈ R$55–80/month** — well within R$500 budget.

---

## Model Selection Principle

- Default: `gpt-4.1-mini` (fast, cheap, structured output support)
- Upgrade to `gpt-4o` / `gpt-4.1` only for: Vision tasks, high-ambiguity turns
- Model configured via env var `SDR_UNDERSTANDING_MODEL`, `SDR_RESPONSE_MODEL`, `SDR_VISION_MODEL`
- Allows hot-swap without code changes

---

## Existing Integration Pattern (from catalog-import)

The existing `openai-extract.ts` provides a proven pattern:
- `json_schema` response format with `strict: true`
- `temperature: 0` for deterministic extraction
- Null-safe output parsing
- Env-driven model selection (`OPENAI_CATALOG_MODEL`)

The SDR Python service should replicate this pattern using the OpenAI Python SDK.

---

## Security Requirements

- API key in env var only (`OPENAI_API_KEY`), never in logs or client
- Raw PII (CPF, renda, endereço) must NOT appear in logs or traces
- Document base64 must NOT be logged
- Signed URLs for stored documents must NOT be logged
- OpenAI data retention: check organization-level "zero data retention" policy if required by client
