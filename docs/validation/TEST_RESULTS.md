# TEST_RESULTS

> 2026-08-26 AFK run

## Python (`apps/sdr`)

```
80 passed
```

Includes: health/webhook auth, merge, decision, handoff, phone/JID, extractor, composer, inventory, media/document (mocked), retention, **10 golden conversation scenarios**.

## Web (`apps/web`)

```
vitest features/sdr: 9 passed (jid-guard + document-access)
npm run typecheck: pass
npm run build: pass
```

## Database

- Migration `20260826120000_sdr_core` applied on local `facilcar-db` via SQL.
- `prisma migrate deploy` against local reported P3005 (baseline needed for migration history) — documented.

## Not run / pending environment

- Live Evolution WhatsApp E2E (QR / session)
- Live OpenAI eval suite (`LIVE_LLM=1` not required for AFK)
- Cloud staging deploy
- Production RLS apply
