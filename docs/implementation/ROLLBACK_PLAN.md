# ROLLBACK_PLAN — SDR Rollback Procedures

## Level 1: Kill Switch (Instant, No Data Loss)

**Use when**: Bot is misbehaving but infrastructure is healthy.

```bash
# Option A: Environment variable
JULIA_ENABLED=false
# Redeploy SDR service (< 30 seconds on VPS)

# Option B: DB flag (faster, no redeploy)
UPDATE facilcar."SiteSettings" SET "juliaEnabled" = false;
# SDR worker polls this flag and stops sending replies
# (requires juliaEnabled field — add in Wave 0)
```

**Effect**: Incoming messages are still received and stored. No customer message is lost. No bot replies are sent. Human sellers take over normally on the same WhatsApp thread.

**Recovery**: Set `JULIA_ENABLED=true` or restore DB flag.

---

## Level 2: Pause SDR Worker Only

**Use when**: Worker is creating bad leads or crashing.

```bash
docker-compose -f docker-compose.sdr.yml stop sdr-worker
# SDR API still receives and stores messages
# Worker simply stops processing — messages queue up
```

**Effect**: Messages accumulate in `Message` table. No replies sent. No Lead state mutations. Resume by starting worker again.

**Recovery**: `docker-compose -f docker-compose.sdr.yml start sdr-worker`

---

## Level 3: Rollback to Previous Image

**Use when**: A new deploy broke the SDR service.

```bash
# Pull previous image tag
docker pull ghcr.io/facilcar/sdr-api:previous-tag
docker-compose -f docker-compose.sdr.yml up -d --force-recreate sdr-api sdr-worker
```

---

## Level 4: Database Migration Rollback

**Use when**: A migration caused issues (unlikely — all additive).

Since all SDR migrations are purely additive (new tables, new columns):
- Dropping new tables does not affect existing functionality
- Existing Lead/Customer/Vehicle tables are untouched

```bash
# Rollback specific migration
cd apps/sdr && alembic downgrade -1

# Or via Prisma (web app migrations)
# Note: Prisma does not support automatic rollback — write a manual down migration
```

**Note**: The `20260504000000_julia_integration` migration is already in production. DO NOT roll it back — it would remove Lead enum values that may already have data.

---

## Level 5: Emergency — Disconnect from Production WhatsApp

**Use when**: SDR is actively harming customer conversations.

```bash
# Delete SDR Evolution instance (stops all WA activity)
curl -X DELETE http://localhost:8081/instance/delete/facilcar-sdr \
  -H "apikey: $EVOLUTION_API_KEY"
```

**Effect**: Evolution disconnects from WhatsApp immediately. No further messages received or sent. Instance can be reconnected via QR scan.

---

## What Cannot Be Rolled Back

| Action | Reason | Mitigation |
|--------|--------|-----------|
| QUALIFIED lead created | Business event, seller may have already engaged | Mark lead `internalNote: "Criado por IA — verificar"` |
| Message stored in DB | Intentional — messages must be preserved | No rollback needed |
| Document uploaded to private bucket | Intentional | Delete via signed URL if needed |
| WON side-effect (vehicle → SOLD) | Standard CRM behavior, predates SDR | Manual vehicle status correction |

---

## Monitoring Checklist (Post-Deploy)

After each wave deploy, verify:
- [ ] `GET /health` → 200
- [ ] No error logs in Evolution container
- [ ] No DB connection errors in SDR logs
- [ ] Test message via dev number (`5545988432998`) → response in < 5s
- [ ] No unexpected QUALIFIED leads (if not in Wave 3+ yet)
