# Security pre-go-live notes (AFK)

## Confirmed risks
- RLS disabled on all `facilcar` tables (production)
- App uses Prisma server-side — safe **if** Data API / service_role never exposed to clients

## Implemented in this run
- Admin-only signed URLs for SdrDocument originals
- LEAD_MANAGER denied original document access (unit tested)
- Webhook secrets for SDR relay
- JULIA_ENABLED kill switch keeps ingest alive
- Retention helpers (no destructive cron yet)

## Required before production activation
1. Audit that `SUPABASE_SERVICE_ROLE_KEY` is server-only
2. Create private `sdr-documents` bucket (public=false)
3. Test RLS enablement on **staging/local** before production
4. Mask CPF in UI (existing lead detail pattern — keep for new fields)
5. Ensure logs never print document base64 / full CPF

Do **not** casually `ENABLE ROW LEVEL SECURITY` on production without verifying Prisma server role bypass / policies.
