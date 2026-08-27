# 18 — Preflight Investigation

## Repo
Verificar package manager, workspaces, Turborepo/Nx, Vercel root, build filters, ignored paths, CI, scripts, Docker e env strategy.

## Prisma
Inspecionar schema, enums, Lead, Customer, FinancingRequest, SellRequest, User, Vehicle e migrations Julia.

## Supabase
Confirmar produção/staging, schemas, Storage, RLS, service role, migrations e pgvector se necessário.

## App web
Mapear Kanban, lead list/detail, auth, RBAC, notificações e APIs.

## Evolution
Confirmar versão, webhook payload, IDs, `fromMe`, group JID, mídia, auth, sendText/sendMedia, reconnect e retries.

## Vercel
Validar se `apps/sdr` interfere no build/deploy.

## Saídas obrigatórias
`REPO_MAP.md`, `SUPABASE_MAP.md`, `EVOLUTION_CONTRACT.md`, `VERCEL_IMPACT.md`, `GAPS.md` e ADRs para novas decisões.
