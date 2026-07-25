# FácilCar — desenvolvimento local

## Pré-requisitos

- Node.js 20+ (recomendado; funciona em versões mais novas com avisos do Prisma)
- Homebrew: `docker`, `colima`, `docker-compose`

## Primeira vez

```bash
# 1) Iniciar runtime Docker (substitui Docker Desktop)
colima start

# 2) Na raiz do repositório facilcar/
npm install
npm run setup          # sobe Postgres, aplica schema (db push) e seed

# 3) App
npm run dev            # http://localhost:3000
```

## Comandos úteis (raiz `facilcar/`)

| Comando | Descrição |
|---------|-----------|
| `npm run dev` | Next.js em modo desenvolvimento |
| `npm run build` | Build de produção |
| `npm run db:up` | Sobe container `facilcar-db` |
| `npm run db:down` | Para containers |
| `npm run db:push` | Sincroniza schema Prisma (dev local) |
| `npm run db:deploy` | Migrations versionadas (Supabase/prod) |
| `npm run db:seed` | Dados demo |
| `npm run db:reset` | Apaga volume, recria DB + push + seed |
| `npm run setup` | `db:up` + wait + push + seed |

## Credenciais demo

- **Admin:** `admin@facilcar.demo` / `ChangeMe123!`
- **Postgres:** `postgresql://postgres:postgres@127.0.0.1:5432/facilcar`

## Variáveis de ambiente

Copie `apps/web/.env.example` → `apps/web/.env` (ou use o `.env` já gerado para local).

Produção/Supabase: use `npm run db:deploy` com `DATABASE_URL` apontando para o Supabase (migrations incluem `storage.*` do Supabase).

## Docker sem Desktop

Este projeto usa **Colima** + **docker-compose** (CLI Homebrew):

```bash
colima start          # se o daemon não estiver rodando
docker-compose ps     # deve listar facilcar-db
```

Se `docker compose` falhar, use `docker-compose` (já configurado nos scripts npm).
