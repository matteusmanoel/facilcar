"""Origin of suspicious Vehicle.model values such as ``View``.

Separation of concerns
----------------------
1. **Read resilience (this SDR run)** — inventory search matches ``title`` as a
   safe fallback when ``model`` is corrupt/suspicious. Never expose non-PUBLISHED.
2. **Existing data cleanup (future)** — one-off SQL/admin job to fix published
   rows whose ``model`` is a UI token; out of scope for conversational fix.
3. **Ingestion prevention (future)** — harden catalog-import so bad tokens never
   become ``Vehicle.model``.

How ``model`` is populated today
--------------------------------
Catalog import (`apps/web/features/catalog-import/server/`):

- ``classify.deterministicParseFromText``: after detecting brand on the first
  line, takes the **first whitespace token** as ``model``.
  Example: ``"Honda Civic 2020"`` → ``Civic``.
  A caption/title like ``"Toyota View ..."`` or a WhatsApp product title that
  starts with UI chrome can yield ``model = "View"``.
- ``openai-extract.ts``: free-form ``model`` from the LLM when deterministic
  parse is incomplete; hybrid path in ``worker.ts`` **replaces** the
  deterministic parse with the AI result (not field-merged).
- ``create-draft.ts``: persists ``model: parsed.model?.trim() || "Não informado"``.

There is **no** literal ``"View"`` in the importer source — the live Corolla row
had ``title = "TOYOTA COROLLA GLI..."`` and ``model = "\\u200eView"`` (U+200E +
``View``), consistent with a bad first-token / caption / product-message title
passing through deterministic or OpenAI extract.

Recommended follow-ups (not this run)
-------------------------------------
- Reject / remap ``SUSPICIOUS_MODEL_TOKENS`` at import time (shared list with SDR).
- Prefer title-derived model when deterministic token is suspicious.
- Additive backfill: set ``model`` from title tokens for PUBLISHED rows where
  ``model`` is suspicious and title contains a clear model token.
"""
