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
3. **Obrigatório para login admin**: `AUTH_SECRET` (mín. ~32 caracteres):
   ```bash
   export AUTH_SECRET="$(openssl rand -base64 32)"
   ```
4. Subir app:
   ```bash
   npm run dev
   ```

**Admin demo (seed):** `admin@facilcar.demo` / `ChangeMe123!`

**Nota técnica:** `/admin/*` usa **`runtime = nodejs`** no layout admin (evita erro edge/crypto com Auth.js + Prisma + bcrypt).

---

## Produção local (`next build` + `next start`)

Simula o que a Vercel executa após o build:

```bash
cd apps/web
export DATABASE_URL="postgres://postgres:postgres@localhost:5432/facilcar?schema=public"
export AUTH_SECRET="$(openssl rand -base64 32)"
npm run build
npm run start
# padrão: http://localhost:3000 — ou: npm run start -- -p 3020
```

Smoke rápido: `/` e `/estoque` → 200; `/admin` sem cookie → redirect para `/admin/login`; `/admin/login` → 200.

---

## Vercel — checklist de publicação

| Campo | Valor |
|-------|--------|
| **Root Directory** | `apps/web` |
| **Framework** | Next.js (detectado) |
| **Install Command** | `npm install` (default no diretório raiz do app) |
| **Build Command** | `npm run build` (default) |
| **Output** | gerenciado pelo Next (sem pasta `out` estática) |

### Variáveis de ambiente (produção)

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `DATABASE_URL` | **Sim** | Postgres (ex.: Neon) |
| `AUTH_SECRET` | **Sim** | `openssl rand -base64 32` |
| `NEXT_PUBLIC_SITE_URL` | **Sim** | URL pública do site |
| `NEXT_PUBLIC_WHATSAPP_NUMBER` | **Sim** | DDI+DDD+número |
| `AUTH_URL` | Opcional | URL pública; com `trustHost: true` no Auth costuma funcionar na Vercel sem |
| `STORAGE_*` | Opcional | R2 presign |
| `RESEND_*` / `LEAD_NOTIFY_EMAIL` | Opcional | E-mail em novo lead |
| `NEXT_PUBLIC_POSTHOG_*` | Opcional | Analytics |
| `SENTRY_DSN` | Opcional | Erros |

### Após o primeiro deploy (banco vazio)

Com `DATABASE_URL` de **produção** no ambiente local ou CI:

```bash
cd apps/web
npx prisma db push
npm run db:seed
```

Isso cria schema + dados demo (inclui usuário admin).

### Auth / callbacks

- Cookies de sessão são **same-site** ao domínio deployado.
- Em HTTPS (Vercel), cookie seguro: `__Secure-next-auth.session-token`.
- Middleware checa ambos os nomes de cookie.

### Smoke pós-deploy

1. `/` — home
2. `/estoque` — catálogo
3. `/contato` — formulário
4. `/api/health` — 200 (corpo com `database: connected`)
5. `/admin/login` — 200
6. Login seed → `/admin`
7. Navegar veículos / leads / páginas / blog
8. **Sair**

---

## Troubleshooting

- **Admin 500 / edge + crypto:** código atual força Node em `/admin/*`; redeploy limpo.
- **Login não persiste:** `AUTH_SECRET` definido; domínio/cookies HTTPS.
- **Build na Vercel com lockfile na raiz do monorepo:** se houver `package-lock.json` na raiz `facilcar` e outro em `apps/web`, a Vercel usa o root do app; em caso de aviso, alinhar lockfile ou `turbopack.root` / `outputFileTracingRoot` conforme doc Next.
