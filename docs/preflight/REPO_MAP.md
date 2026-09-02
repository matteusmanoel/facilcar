# REPO_MAP — FacilCar Monorepo

> Generated: 2026-08-25 (preflight run)

## Root Structure

```
facilcar/
├── apps/
│   └── web/                   # Next.js 16 app — the ONLY app in the monorepo today
├── docs/                      # Project docs (catalog-import-whatsapp.md, contrato)
├── julia_sdr_master_pack/     # SDR product discovery, docs, tests, prompts
├── alx_mvp_docs/              # Legacy MVP docs
├── scripts/                   # Root-level scripts (wait-for-postgres, evolution-import-creds)
├── supabase/                  # Root-level Supabase CLI config (see SUPABASE_MAP for issue)
├── docker-compose.yml         # Local Postgres for development (pg:16, port 5432)
├── docker-compose.evolution.yml  # Evolution API v2.3.7 stack (pg:15 + redis:7 + evolution)
├── package.json               # Root npm scripts delegating to apps/web
├── package-lock.json          # npm lockfile (root, minimal — only root installs)
├── pnpm-lock.yaml             # EMPTY pnpm lockfile — package manager conflict, see below
├── sdr-knowledge-sources.md   # Authoritative pre-flight investigation output (read-only)
└── .env.evolution[.example]   # Evolution API secrets
```

## Package Manager Situation

| File | Status | Risk |
|------|--------|------|
| `package-lock.json` (root) | Active — root installs only | Low |
| `apps/web/package-lock.json` | Active — all web dependencies | Low |
| `pnpm-lock.yaml` (root) | **Present but EMPTY** (only settings header) | **Medium** |

**Finding**: The monorepo uses **npm** via the root `package.json` postinstall delegation pattern, NOT pnpm workspaces. The `pnpm-lock.yaml` at root is a leftover from an earlier pnpm attempt; it contains no packages. Running `pnpm install` at root would produce no-op. The coexistence of both lockfiles is a minor risk but does not affect current npm-based operations.

**Recommendation**: Remove `pnpm-lock.yaml` from root or add it to `.gitignore`. Do NOT introduce pnpm workspaces unless the monorepo is restructured.

## apps/web Structure

```
apps/web/
├── app/
│   ├── admin/
│   │   ├── (dashboard)/
│   │   │   ├── leads/          # List + Kanban + detail + novo
│   │   │   ├── veiculos/       # Vehicle CRUD
│   │   │   ├── crm/            # Redirects → /admin/leads?view=kanban
│   │   │   ├── configuracoes/  # SiteSettings
│   │   │   ├── usuarios/       # User management
│   │   │   ├── blog/           # BlogPost CRUD
│   │   │   └── paginas/        # Page CRUD
│   │   ├── layout.tsx          # runtime = "nodejs"
│   │   └── login/
│   ├── api/
│   │   ├── admin/upload/       # Image upload (S3/R2)
│   │   ├── auth/               # NextAuth handlers
│   │   ├── health/             # Health check
│   │   └── webhooks/evolution/ # Catalog import webhook (NOT SDR)
│   └── (public)/               # Catalog, forms, blog, etc.
├── components/
│   ├── admin/
│   │   ├── Kanban/             # KanbanBoard, KanbanCard, KanbanBoardLoader
│   │   ├── AdminShell.tsx      # Admin navigation shell
│   │   └── ...
│   └── ui/                     # Radix-based UI components
├── features/
│   ├── admin/server/           # brands.ts, customers.ts
│   ├── auth/server/            # rbac.ts, rbac-config.ts
│   ├── catalog/server/         # queries.ts (Vehicle PUBLISHED only)
│   ├── catalog-import/server/  # Full Evolution→Vehicle import pipeline
│   ├── customer/server/        # upsert.ts (Customer by phone)
│   ├── lead/server/            # queries.ts, mutations.ts
│   ├── settings/               # SiteSettings
│   ├── storage/server/         # S3 upload, presign
│   └── vehicle/server/         # queries.ts
├── prisma/
│   ├── schema.prisma           # All models (see CURRENT_DOMAIN_MAP)
│   ├── migrations/             # 8 versioned migrations
│   └── seed.ts / seed-prod.ts
├── schemas/                    # Zod schemas (brand, lead, etc.)
├── lib/
│   ├── db.ts                   # Prisma client singleton
│   └── query-filters.ts
└── scripts/                    # catalog-import scripts
```

## TypeScript Configuration

- Target: ES2017
- Module resolution: `bundler` (Next.js)
- Strict mode: enabled
- Path alias: `@/*` → `./` (relative to apps/web)
- No project references; single tsconfig for all apps/web

## Workspace Configuration

**Not a pnpm/Turborepo/Nx workspace.** The root `package.json` uses npm scripts with `--prefix apps/web`. No `workspaces` field. No `turbo.json`. No `nx.json`.

Implication: Adding `apps/sdr` (Python) requires **no workspace changes** — Python is managed independently. A new `apps/sdr/` directory can be created with its own `pyproject.toml`/`requirements.txt` without touching the npm setup.

## Scripts Available at Root

| Script | What it does |
|--------|-------------|
| `npm run dev` | `next dev` in apps/web |
| `npm run build` | `next build` in apps/web |
| `npm run db:up/down` | Docker compose for local Postgres |
| `npm run evolution:up/down` | Evolution API stack |
| `npm run evolution:import-creds` | Import WA credentials via script |
| `npm run catalog-import:worker` | Run catalog import worker (tsx) |
| `npm run test:unit` | Vitest unit tests in apps/web |

## CI/CD

No `.github/`, `.circleci/` or similar CI config found. Deployments go through Vercel (automatic on git push). No pipeline for Python services exists yet.

## Vercel Project

- Project ID: `prj_wsZpNsGxuV81etDVFSzBu4S1ZNvM`
- Org ID: `team_U7JOfalB4XvfDKBwsMVT6Wa3`
- Project name: `facilcar`
- Root Directory: inferred as `apps/web` (no root `vercel.json`; root has no `next.config.*`; deploy works per HANDOFF.md)
- Framework: Next.js
- See `VERCEL_IMPACT.md` for SDR impact analysis.
