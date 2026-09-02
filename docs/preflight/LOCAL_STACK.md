# LOCAL_STACK — Local Development Environment

## Host Machine

- OS: macOS (Apple Silicon, Rosetta 2 supported)
- Container runtime: Colima
- Docker Compose: standard

## Colima Start Command

```bash
colima start --cpu 4 --memory 8 --vm-type=vz --vz-rosetta
```

## Resource Budget (4 CPU / 8 GB RAM)

| Service | CPU | RAM (est.) | Required? |
|---------|-----|-----------|-----------|
| Postgres (Supabase local DB) | 0.2 | 256 MB | ✅ Core |
| Supabase Auth | 0.1 | 128 MB | Only if JWT auth needed for SDR |
| Supabase Storage API | 0.1 | 128 MB | Only for document bucket tests |
| Redis | 0.1 | 64 MB | ✅ Core (locks, debounce, idempotency) |
| Evolution API | 0.3 | 256 MB | ✅ For integration/smoke tests |
| Evolution Postgres | 0.2 | 128 MB | ✅ (bundled with Evolution) |
| Evolution Redis | 0.1 | 64 MB | ✅ (bundled with Evolution) |
| SDR FastAPI (sdr-api) | 0.3 | 256 MB | ✅ Core |
| SDR Worker | 0.3 | 256 MB | ✅ Core |
| Next.js app (dev) | 0.5 | 512 MB | Optional — only when testing CRM changes |
| **Total** | **~2.2** | **~2.1 GB** | Leaves ~6GB headroom |

**Conclusion**: The local stack fits comfortably in 4 CPU / 8 GB. Run the Next.js app only when testing web CRM features.

---

## Minimal Supabase Local Profile

Supabase CLI v2.110.0 is installed.

For SDR development, start Supabase excluding heavy services:

```bash
supabase start \
  --exclude storage,imgproxy,edge-runtime,logflare,vector,supavisor,studio
```

This gives you:
- ✅ Postgres (port 54322)
- ✅ Auth (port 54321 — only if needed)
- ✅ REST API (PostgREST — only if SDR uses it)
- ❌ Studio, Storage, Edge Functions, Analytics (not needed for SDR core)

**Alternative — skip Supabase local entirely**: Use a `.env.local` pointing to the staging Supabase project. Faster startup, no local Postgres, but requires internet access.

**Recommended for SDR team**: Use the staging Supabase project for unit dev (fast) and only spin up local Supabase for migration testing.

---

## Docker Compose Profiles (Proposed)

Create `docker-compose.sdr.yml` at repo root:

```yaml
# profiles:
#   core:        Postgres + Redis + SDR API + SDR Worker
#   integration: + Evolution API
#   full:        + Next.js app
```

Commands:
```bash
# Core SDR dev
docker-compose -f docker-compose.sdr.yml --profile core up -d

# Integration smoke tests (includes Evolution)
docker-compose -f docker-compose.sdr.yml -f docker-compose.evolution.yml --profile integration up -d
```

---

## Service Ports

| Service | Local Port | Notes |
|---------|-----------|-------|
| Postgres (local dev / docker-compose.yml) | 5432 | facilcar DB |
| Supabase Postgres (supabase local) | 54322 | If using supabase local |
| Redis (SDR) | 6379 | SDR locks/cache |
| Evolution API | 8081 | Existing (docker-compose.evolution.yml) |
| SDR FastAPI | 8000 | New service |
| SDR Worker | — | Background process, no HTTP port |
| Next.js dev | 3000 | apps/web |

---

## Environment Files

| File | Purpose | Gitignored? |
|------|---------|------------|
| `.env.evolution` | Evolution API secrets | ✅ (template: `.env.evolution.example`) |
| `apps/web/.env` | Next.js web app | ✅ (template: `.env.example`) |
| `apps/sdr/.env` | SDR Python service | ✅ (create `apps/sdr/.env.example`) |

### Proposed `apps/sdr/.env.example`

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/facilcar?schema=facilcar

# Redis
REDIS_URL=redis://localhost:6379/0

# Supabase (for Storage access)
SUPABASE_URL=https://oulknepjqhyiyjbiuqtg.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>

# Evolution API
EVOLUTION_API_URL=http://localhost:8081
EVOLUTION_API_KEY=<same as AUTHENTICATION_API_KEY in .env.evolution>
EVOLUTION_SDR_INSTANCE=facilcar-sdr

# OpenAI
OPENAI_API_KEY=<key>
SDR_UNDERSTANDING_MODEL=gpt-4.1-mini
SDR_RESPONSE_MODEL=gpt-4.1-mini
SDR_VISION_MODEL=gpt-4o

# SDR Config
SDR_WEBHOOK_SECRET=<random>
JULIA_ENABLED=true
SDR_DEBOUNCE_MS=1500
SDR_LOCK_TTL_SECONDS=60
SDR_MAX_TURNS_IN_CONTEXT=10
```

---

## WhatsApp Test Number

Development: `5545988432998` — use ONLY for local/staging tests. Never connect this to production traffic.

---

## Setup Command Sequence

```bash
# 1. Start Colima
colima start --cpu 4 --memory 8 --vm-type=vz --vz-rosetta

# 2. Start Evolution + SDR stack
npm run evolution:up
docker-compose -f docker-compose.sdr.yml up -d

# 3. Run SDR DB migrations (from apps/sdr)
cd apps/sdr && alembic upgrade head

# 4. Start SDR services
uvicorn sdr.main:app --reload --port 8000 &
python -m sdr.worker &

# 5. Optional: Start Next.js app
npm run dev
```
