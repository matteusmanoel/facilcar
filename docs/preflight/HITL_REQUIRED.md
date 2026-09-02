# HITL_REQUIRED — Questions Requiring Human Confirmation

> Generated: 2026-08-25 (preflight)
> Updated: 2026-08-26 (AFK run) — all three questions **RESOLVED** by human.

---

## HITL-001: Staging Supabase Project Identity — RESOLVED

**STATUS**: `RESOLVED` (2026-08-26)

**ANSWER**
Supabase project `munnfnfudrsoblwgivjn` is an **older legacy project** from the historical n8n implementation. It contains RPC functions, RAG records and experimental work. It is **intentionally PAUSED**.

**BINDING RULES**

- DO NOT depend on it.
- DO NOT reactivate it.
- DO NOT treat it as staging.
- DO NOT migrate the new architecture into it.
- It may later be reactivated after Supabase Pro is purchased only to retrieve historical references — **outside this MVP**.

**AUTHORITATIVE PRODUCTION**: `oulknepjqhyiyjbiuqtg` (already verified by pre-flight).

**STAGING**: Separate staging project remains an architecture goal. Until provisioned by a human (account/billing), use local Supabase + `ENVIRONMENT_PENDING` for cloud staging smoke. Do not use production as staging substitute. Do not use the paused project.

**BLOCKS**: External staging provisioning only — not Waves 0–7 code.

---

## HITL-002: Commercial Playbook Validation — RESOLVED

**STATUS**: `RESOLVED` (2026-08-26)

**ANSWER**
**Milton Barrios** is the commercial / operational sign-off validator before production activation.

**BINDING RULES**

- Implementation proceeds without waiting for Milton.
- Commercial validation remains a **hard go-live gate** (Wave 9 / production activation).
- Deliver `docs/validation/MILTON_PLAYBOOK_VALIDATION.md` for his review.

**BLOCKS**: Production activation only — not coding Waves 0–8.

---

## HITL-003: SDR Webhook Architecture — RESOLVED

**STATUS**: `RESOLVED` (2026-08-26)

**ANSWER**

- **MVP / current phase**: **VERCEL RELAY** (Evolution → Next.js webhook → persistence → SDR worker).
- **Future (after Hostinger VPS contracted)**: **DIRECT TO VPS**.

**BINDING RULES**

- Keep transport **configuration-driven**.
- Do **not** couple Python domain/application layers to Vercel.
- Migration to direct VPS must not rewrite domain logic (ADR-002).

**BLOCKS**: Nothing for MVP code. Production routing switch is a post-VPS ops step.

---

## Summary

| ID       | Status                           | Impact                              |
| -------- | -------------------------------- | ----------------------------------- |
| HITL-001 | RESOLVED — paused legacy; ignore | Staging cloud = ENVIRONMENT_PENDING |
| HITL-002 | RESOLVED — Milton validates      | Go-live commercial gate             |
| HITL-003 | RESOLVED — Vercel relay MVP      | Config-driven transport             |

**Implementation readiness**: `READY` for Waves 0–7 code.
