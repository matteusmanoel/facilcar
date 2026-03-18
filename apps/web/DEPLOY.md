# Deploy (Vercel) e operação local

## Dev local com Docker (Postgres)

1. Na **raiz do repo**:
   ```bash
   docker compose up -d db
   ```
2. Em **`apps/web`**, com `DATABASE_URL` (inline ou `.env`):
   ```bash
   DATABASE_URL="postgres://postgres:postgres@localhost:5432/facilcar?schema=public"
   npm run db:push
   npm run db:seed
   ```
3. **Obrigatório para login admin**: `AUTH_SECRET` (ex.: `openssl rand -base64 32`). Sem isso, Auth.js não emite sessão válida.
4. Subir app:
   ```bash
   npm run dev
   ```
   Ou validar como produção:
   ```bash
   npm run build && npm run start
   ```

**Admin demo (seed):** `admin@autodealerdemo.com` / `ChangeMe123!`

**Nota técnica:** `/admin/*` usa **`runtime = nodejs`** no layout admin para não empacotar NextAuth/Prisma/bcrypt no runtime Edge (evita erro `crypto`).

---

## Vercel

1. **Root Directory** = `apps/web`.
2. **Build**: `npm run build`. **Install**: `npm install` no diretório do app.
3. **Variáveis de ambiente**:

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `DATABASE_URL` | Sim | Postgres (ex.: Neon) |
| `AUTH_SECRET` | Sim | `openssl rand -base64 32` |
| `AUTH_URL` | Recomendado | URL pública; com `trustHost: true` no Auth, Vercel costuma funcionar sem |
| `NEXT_PUBLIC_SITE_URL` | Sim | URL pública |
| `NEXT_PUBLIC_WHATSAPP_NUMBER` | Sim | DDI+DDD+número |
| `STORAGE_*` | Opcional | R2 presign |
| `RESEND_*` / `LEAD_NOTIFY_EMAIL` | Opcional | E-mail em novo lead |
| `NEXT_PUBLIC_POSTHOG_*` | Opcional | Analytics |
| `SENTRY_DSN` | Opcional | Erros |

4. **Banco após primeiro deploy** (com `DATABASE_URL` de produção):
   ```bash
   cd apps/web && npx prisma db push && npm run db:seed
   ```
   Ou `prisma migrate deploy` quando houver migrations versionadas.

5. **Smoke**: `/`, `/estoque`, `/contato`, `/api/health`, `/admin/login` → login → `/admin`.

## Troubleshooting

- **Admin 500 / edge + crypto**: garantir deploy com código atual (layout admin `runtime = nodejs`). Em dev, se houver lock de outro `next dev`, encerre processos antigos.
- **Login não persiste**: conferir `AUTH_SECRET` e cookies (mesmo domínio / HTTPS em produção).
