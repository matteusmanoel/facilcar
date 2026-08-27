# ADR-002: SDR Webhook — Relay via Next.js (MVP) vs Direct VPS (Production)

**Status**: Accepted for MVP; revisit for production
**Date**: 2026-08-25
**HITL-003**: RESOLVED 2026-08-26 — Vercel relay for MVP; direct VPS after Hostinger is contracted. Transport must remain configuration-driven; Python domain must not couple to Vercel.

## Context

Evolution API sends webhooks to one URL per instance. The SDR Python service needs to receive these webhooks. Two deployment options exist:

- **Option A (Relay)**: Evolution → Vercel (`/api/webhooks/sdr`) → DB insert → Python worker polls
- **Option B (Direct)**: Evolution → VPS FastAPI directly

The VPS is not yet provisioned (D-014).

## Decision for MVP

Use **Option A (Relay)** via Vercel Next.js for the initial launch.

## Rationale

1. **No VPS required immediately**: Pilot can start without provisioning the VPS.
2. **Vercel is already live**: Zero additional infrastructure for the webhook receiver.
3. **Reliability**: Vercel has automatic SSL, DDoS protection, and uptime guarantees.
4. **Message durability**: Webhook stores to Postgres immediately; Python worker processes asynchronously. No message loss even if Python service is slow/down.
5. **Migration path is trivial**: When VPS is ready, update the Evolution webhook URL. Zero code changes.

## Production Migration (Wave 8+)

When Hostinger VPS is provisioned:
1. Configure TLS on VPS
2. Update Evolution webhook URL to point to `https://vps-domain.com/webhook/evolution`
3. Disable relay endpoint in Next.js (or keep as backup)

## Consequences

- ~50ms extra latency per message (Vercel → DB → Python poll). Acceptable for MVP.
- Vercel serverless function handles webhook (stateless, reliable).
- Python worker polls DB every 1–2 seconds (vs immediate push). Acceptable.
- Must set `SDR_WEBHOOK_SECRET` in both Vercel env and Evolution webhook config.
