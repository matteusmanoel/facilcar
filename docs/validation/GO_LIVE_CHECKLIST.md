# GO_LIVE_CHECKLIST

## Blockers (must be done by human)

- [ ] Milton signs `MILTON_PLAYBOOK_VALIDATION.md`
- [ ] Hostinger VPS purchased + TLS + `docker-compose.sdr.prod.yml`
- [ ] Staging Supabase project created (not the paused legacy project)
- [ ] Private bucket `sdr-documents` created
- [ ] Prisma migrations applied to staging then production (with backup)
- [ ] RLS plan tested on staging / accepted mitigation documented
- [ ] Production WhatsApp webhook URL set (Vercel relay or direct VPS)
- [ ] Secrets rotated; service_role never in browser
- [ ] `JULIA_ENABLED` pilot plan confirmed (100% new conversations)

## Technical smoke after cutover

- [ ] Health endpoints green
- [ ] Test message on production number supervised
- [ ] Rollback: `JULIA_ENABLED=false` works without losing inbound store
- [ ] Catalog-import webhook still intact (`/api/webhooks/evolution`)
