# FacilCar SDR (`apps/sdr`)

Python 3.12 FastAPI service for Júlia SDR (webhook ingress + worker).

Prisma is the sole DB migration authority (ADR-003). This service uses asyncpg only — no Alembic.

## Local setup

```bash
cd apps/sdr
python3 -m venv .venv   # prefer 3.12+ (Dockerfile pins 3.12)
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Run API

```bash
uvicorn sdr.main:app --reload --port 8000
```

## Tests (no live DB required)

```bash
cd apps/sdr
pytest -q
```

## Docker (repo root)

```bash
docker compose -f docker-compose.sdr.yml --profile core up -d --build
curl -s http://localhost:8000/health
```

Services are named `facilcar-sdr-*` so they do not collide with Evolution compose.
