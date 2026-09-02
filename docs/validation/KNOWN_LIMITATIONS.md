# KNOWN_LIMITATIONS

1. **Heuristic understanding** when OpenAI key missing — good for tests; production should set `OPENAI_API_KEY`.
2. **Vehicle model list** in heuristics is finite — rare models need LLM path.
3. **Catalog Julia fields** still empty in production — do not treat as policy.
4. **Staging cloud** not provisioned — local only.
5. **RLS** still off on `facilcar` tables — pre-go-live security gate.
6. **Private bucket** `sdr-documents` not auto-created — create in Supabase UI.
7. **Retention purge** is helper/dry-run oriented — schedule ops later.
8. **Prisma migrate history** on local Docker may need baseline before `migrate deploy`.
9. **Real-time notifications** use polling (~15s), not Supabase Realtime.
10. **Paused project** `munnfnfudrsoblwgivjn` intentionally unused (legacy n8n/RAG).

## Seed engine enrichment (authoritative Supabase, 2026-08-27)

Controlled fills only — no regex backfill. Title/model/version/priceCash/status/images unchanged.

| Vehicle id | Title (sanitized) | Previous | New | Evidence |
|---|---|---|---|---|
| `cmsuev4980026vm24shr68ui1` | TOYOTA COROLLA GLI 2.0 AUTOMÁTICO • 2016 | NULL | 2.0 | single `2.0` in title; AUTOMÁTICO is transmission |
| `cmstky8xb000wxb245wkftn8e` | GM MERIVA 1.8 COMPLETA 2005 | NULL | 1.8 | single `1.8` in title |

Q5 2.0 TFSI and other compound labels remain NULL.

## Open conversational / go-live limitations

1. Live replay of “Tem automático?” must be repeated after the SQL VehicleType guard.
2. `vehicle_type` still collides semantically with transmission (propulsion vs Prisma `Vehicle.type`).
3. `ConversationContextBuilder` is not fully wired into the composer/understanding path.
4. Debounce / late-arrival rebatch is pending.
5. Seed `model`/`version`/`type` are inconsistent (e.g. Corolla stored as `GLI`).
6. Origin of the 912 Lead rows is not classified.
7. RLS remains a go-live gate (`facilcar.Vehicle` has RLS off; anon/authenticated have no table GRANT).
