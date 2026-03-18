# Handoff — MVP Auto Dealer (atualizado)

**Última atualização:** 18/03/2026

## Estado atual

- **Build / typecheck / lint**: `npm run build`, `npm run typecheck`, `npm run lint` em `apps/web` estáveis.
- **Banco local**: `docker compose up -d db` na raiz → Postgres `facilcar` em `localhost:5432`.
- **Prisma**: sem pasta `migrations/` versionada; usar `npm run db:push` + `npm run db:seed` com `DATABASE_URL` apontando para o Postgres.
- **Admin / Auth.js**: segmento `/admin/*` roda com **`export const runtime = "nodejs"`** em `app/admin/layout.tsx` (evita erro edge/crypto ao importar NextAuth + Prisma + bcrypt). API Auth e presign R2 também em Node.
- **Middleware**: só checagem de cookie `next-auth.session-token` / `__Secure-next-auth.session-token` + redirect para `/admin/login` (sem importar config Auth).
- **Login demo (seed)**: `admin@autodealerdemo.com` / `ChangeMe123!`
- **Logout**: botão **Sair** no header do dashboard admin (`adminSignOutAction`).
- **Público**: catálogo, leads, blog, páginas institucionais; ver `QA_CHECKLIST.md`.

## Demo local (resumo)

```bash
# 1) Postgres
cd /path/to/facilcar && docker compose up -d db

# 2) Schema + seed (DATABASE_URL inline se não usar .env)
cd apps/web
export DATABASE_URL="postgres://postgres:postgres@localhost:5432/facilcar?schema=public"
npm run db:push && npm run db:seed

# 3) Auth: defina AUTH_SECRET (obrigatório para sessão/login)
export AUTH_SECRET="$(openssl rand -base64 32)"

# 4) App
npm run dev
# ou produção local: npm run build && npm run start
```

## Deploy / QA

- `apps/web/DEPLOY.md`, `apps/web/QA_CHECKLIST.md`

## Opcional

- Sentry, Turnstile, UI de upload R2 no admin, migrations versionadas.
