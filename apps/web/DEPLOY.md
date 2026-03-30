# FácilCar — Guia de Deploy MVP

> Atualizado em: 30/03/2026

---

## Visão geral da arquitetura

| Camada | Serviço recomendado | Alternativa |
|--------|---------------------|-------------|
| Hosting | **Vercel** (Hobby/Pro) | Railway, Render |
| Banco de dados | **Supabase** (Postgres) | Neon, Railway Postgres |
| Storage de imagens | **Supabase Storage** (S3-compat.) | Cloudflare R2 |
| E-mail (leads) | **Resend** | SendGrid, Nodemailer+SMTP |
| Analytics | PostHog | Plausible, GA4 |
| Monitoramento | Sentry | Axiom |

---

## 1. Pré-requisitos locais

```bash
node --version   # ≥ 20
npm --version    # ≥ 10
```

---

## 2. Desenvolvimento local

### 2.1 Postgres local via Docker

Na raiz do repo:

```bash
docker compose up -d db
```

### 2.2 Variáveis de ambiente locais

Em `apps/web`, copie e ajuste:

```bash
cp .env.example .env.local
```

Mínimo obrigatório para rodar:

```env
DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:5432/facilcar"
AUTH_SECRET="$(openssl rand -base64 32)"
AUTH_URL="http://localhost:3000"
NEXT_PUBLIC_SITE_URL="http://localhost:3000"
NEXT_PUBLIC_WHATSAPP_NUMBER="5545999999999"
```

### 2.3 Inicializar banco e seed

```bash
cd apps/web
npx prisma db push       # cria schema
npm run db:seed          # cria usuário admin + dados demo
npm run dev              # inicia em http://localhost:3000
```

**Credenciais admin padrão:** `admin@facilcar.demo` / `ChangeMe123!`

---

## 3. Supabase — Banco de dados

1. Crie um projeto em [supabase.com](https://supabase.com)
2. Acesse **Settings → Database → Connection string**
3. Copie a **URI** (mode: URI, Session pooler para produção):

```env
DATABASE_URL="postgresql://postgres.PROJ_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?pgbouncer=true&sslmode=require"
```

> Para migrations (`prisma migrate deploy`), use a conexão **direta** (porta 5432):
> ```env
> DATABASE_URL="postgresql://postgres:PASSWORD@db.PROJ_REF.supabase.co:5432/postgres?sslmode=require"
> ```

### Configurar schema

Com a URL de produção:

```bash
DATABASE_URL="<url_direta>" npx prisma migrate deploy
DATABASE_URL="<url_direta>" npm run db:seed
```

Ou via painel Supabase → SQL Editor, execute o output de `npx prisma migrate diff`.

---

## 4. Supabase Storage — Imagens de veículos

1. No painel Supabase, vá em **Storage → Create a new bucket**
2. Nome: `vehicle-images`, marque **Public**
3. Em **Settings → Storage → S3 connection**, gere as credenciais

```env
NEXT_PUBLIC_SUPABASE_URL="https://PROJ_REF.supabase.co"
NEXT_PUBLIC_SUPABASE_ANON_KEY="eyJ..."
NEXT_PUBLIC_SUPABASE_HOST="PROJ_REF.supabase.co"

STORAGE_ENDPOINT="https://PROJ_REF.supabase.co/storage/v1/s3"
STORAGE_S3_REGION="us-east-1"
STORAGE_BUCKET_NAME="vehicle-images"
STORAGE_ACCESS_KEY="<access_key>"
STORAGE_SECRET_KEY="<secret_key>"
STORAGE_PUBLIC_URL="https://PROJ_REF.supabase.co/storage/v1/object/public/vehicle-images"
```

Adicione o host ao `next.config.mjs` em `images.remotePatterns`:

```js
{ protocol: "https", hostname: "PROJ_REF.supabase.co" }
```

### Alternativa: Cloudflare R2

```env
STORAGE_ENDPOINT="https://ACCOUNT_ID.r2.cloudflarestorage.com"
STORAGE_BUCKET_NAME="vehicle-images"
STORAGE_ACCESS_KEY="<access_key>"
STORAGE_SECRET_KEY="<secret_key>"
STORAGE_PUBLIC_URL="https://pub-HASH.r2.dev"
```

---

## 5. E-mail de notificação de leads (Resend)

1. Crie conta em [resend.com](https://resend.com)
2. Adicione e verifique seu domínio
3. Gere uma API Key

```env
RESEND_API_KEY="re_..."
RESEND_FROM_EMAIL="noreply@seudominio.com.br"
LEAD_NOTIFY_EMAIL="vendas@seudominio.com.br"
```

> Sem essas variáveis o sistema funciona normalmente — apenas as notificações por e-mail são desabilitadas silenciosamente.

---

## 6. Deploy na Vercel

### 6.1 Importar projeto

1. Acesse [vercel.com/new](https://vercel.com/new)
2. Conecte o repositório GitHub
3. Configure:

| Campo | Valor |
|-------|-------|
| **Root Directory** | `apps/web` |
| **Framework** | Next.js (auto-detectado) |
| **Build Command** | `npm run build` |
| **Install Command** | `npm install` |
| **Output Directory** | _(deixe padrão)_ |

### 6.2 Variáveis de ambiente na Vercel

Vá em **Settings → Environment Variables** e adicione:

#### Obrigatórias

| Variável | Valor |
|----------|-------|
| `DATABASE_URL` | URL do pooler Supabase/Neon |
| `AUTH_SECRET` | `openssl rand -base64 32` |
| `NEXT_PUBLIC_SITE_URL` | `https://seudominio.com.br` |
| `NEXT_PUBLIC_WHATSAPP_NUMBER` | `5545999999999` (DDI+DDD+número) |

#### Storage (para upload de imagens)

| Variável | Valor |
|----------|-------|
| `NEXT_PUBLIC_SUPABASE_URL` | URL do projeto Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Chave anon pública |
| `NEXT_PUBLIC_SUPABASE_HOST` | Host do Supabase |
| `STORAGE_ENDPOINT` | Endpoint S3 do Storage |
| `STORAGE_S3_REGION` | Região |
| `STORAGE_BUCKET_NAME` | Nome do bucket |
| `STORAGE_ACCESS_KEY` | Chave de acesso |
| `STORAGE_SECRET_KEY` | Chave secreta |
| `STORAGE_PUBLIC_URL` | URL pública dos objetos |

#### Opcionais

| Variável | Descrição |
|----------|-----------|
| `AUTH_URL` | URL pública para Auth.js (geralmente não necessário na Vercel) |
| `RESEND_API_KEY` | Notificações de leads |
| `RESEND_FROM_EMAIL` | E-mail remetente |
| `LEAD_NOTIFY_EMAIL` | E-mail receptor de leads |
| `NEXT_PUBLIC_POSTHOG_KEY` | Analytics |
| `NEXT_PUBLIC_POSTHOG_HOST` | Host PostHog |
| `SENTRY_DSN` | Monitoramento de erros |

### 6.3 Domínio customizado

1. **Settings → Domains → Add**
2. Adicione `seudominio.com.br` e `www.seudominio.com.br`
3. Configure os registros DNS conforme exibido (CNAME ou A record)
4. HTTPS é provisionado automaticamente pelo Vercel

---

## 7. Após o primeiro deploy

### 7.1 Inicializar banco de produção

Com a DATABASE_URL direta (sem pooler) no terminal local:

```bash
cd apps/web
DATABASE_URL="postgresql://postgres:SENHA@db.PROJ_REF.supabase.co:5432/postgres?sslmode=require" \
  npx prisma migrate deploy

DATABASE_URL="postgresql://postgres:SENHA@db.PROJ_REF.supabase.co:5432/postgres?sslmode=require" \
  npm run db:seed
```

### 7.2 Alterar senha do admin

Acesse `/admin/login` com as credenciais do seed e altere a senha em **Configurações**.

> **Importante:** Remova ou desative o usuário demo em produção.

---

## 8. Smoke test pós-deploy

Execute manualmente após cada deploy:

- [ ] `GET /` — home carrega com veículos em destaque
- [ ] `GET /estoque` — catálogo carrega com filtros funcionais
- [ ] `GET /estoque/[slug]` — página de veículo com galeria e botão WhatsApp
- [ ] `GET /financiamento` — formulário de simulação funcional
- [ ] `GET /contato` — formulário de contato funcional
- [ ] `GET /api/health` — retorna `{ "database": "connected" }`
- [ ] `GET /admin` → redireciona para `/admin/login` (não autenticado)
- [ ] Login admin → `/admin` carrega dashboard com stats
- [ ] Criar veículo → slug gerado automaticamente, imagens upadas
- [ ] Lead criado aparece em `/admin/leads` (lista e kanban)
- [ ] Dark mode toggle funciona no admin
- [ ] `GET /sitemap.xml` — retorna XML com URLs dos veículos publicados
- [ ] `GET /robots.txt` — retorna regras corretas

---

## 9. Operações de manutenção

### Migrations

```bash
# Criar nova migration (desenvolvimento)
cd apps/web
npx prisma migrate dev --name nome_da_migracao

# Aplicar em produção
DATABASE_URL="<url_direta_prod>" npx prisma migrate deploy
```

### Backup do banco

No painel Supabase: **Database → Backups** (plano Pro inclui backups diários automáticos).

Para exportar manualmente:

```bash
pg_dump "postgresql://postgres:SENHA@db.PROJ_REF.supabase.co:5432/postgres" \
  --no-owner -Fc -f backup_$(date +%Y%m%d).dump
```

### Seed apenas do usuário admin

```bash
DATABASE_URL="<url_prod>" node -e "
const { PrismaClient } = require('@prisma/client');
const bcrypt = require('bcryptjs');
const prisma = new PrismaClient();
async function main() {
  const hash = await bcrypt.hash('SenhaNova123!', 12);
  await prisma.adminUser.upsert({
    where: { email: 'admin@seudominio.com.br' },
    update: { passwordHash: hash },
    create: { email: 'admin@seudominio.com.br', name: 'Admin', passwordHash: hash }
  });
  console.log('Admin criado/atualizado');
}
main().finally(() => prisma.\$disconnect());
"
```

---

## 10. Troubleshooting

| Sintoma | Causa provável | Solução |
|---------|---------------|---------|
| Build falha com erro de crypto/edge | Auth.js com bcrypt | Verificar `runtime = "nodejs"` no layout admin |
| Login não persiste em produção | `AUTH_SECRET` diferente entre builds | Definir secret fixo na Vercel (não regen) |
| Upload de imagens falha | Variáveis `STORAGE_*` ausentes ou bucket não público | Verificar bucket público e credenciais S3 |
| Leads não notificam por e-mail | `RESEND_*` não configurado | Adicionar variáveis na Vercel |
| `/api/health` retorna DB desconectado | `DATABASE_URL` incorreta ou limite de conexões | Usar pooler Supabase (pgbouncer=true) |
| Imagens não carregam | Host não em `next.config.mjs` `remotePatterns` | Adicionar hostname do storage |
| Slug duplicado ao criar veículo | Auto-incremente aplicado (`-1`, `-2`) | Normal — sistema resolve automaticamente |
| Vercel build timeout | Pacotes pesados | Aumentar timeout em `vercel.json`: `{"buildCommand": "npm run build", "functions": {"api/**": {"maxDuration": 30}}}` |

---

## 11. Checklist final MVP

- [ ] Banco de produção inicializado com `migrate deploy` + seed
- [ ] `AUTH_SECRET` seguro e fixo (não regenerado a cada deploy)
- [ ] Usuário admin com senha forte (não o seed demo)
- [ ] Storage configurado e bucket público
- [ ] Domínio customizado com HTTPS
- [ ] Variáveis de ambiente configuradas na Vercel
- [ ] WhatsApp configurado nos settings do admin (`/admin/configuracoes`)
- [ ] Informações da loja preenchidas (nome, endereço, contato)
- [ ] Pelo menos 1 veículo publicado no estoque
- [ ] Notificação de e-mail de leads testada (ou documentada como pendente)
- [ ] Google Analytics ou PostHog configurado (recomendado)
- [ ] Smoke test completo executado
- [ ] `robots.txt` e `sitemap.xml` verificados
- [ ] Imagem OG configurada no settings SEO
