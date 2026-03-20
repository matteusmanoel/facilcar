# Runbook — Demo MVP FácilCar

Guia para operacionalizar, testar e apresentar a demo (local + staging).

## 1. Pré-requisitos

- Node.js compatível com o projeto
- Docker (Postgres local)
- Conta Vercel + Postgres gerenciado (Neon/Supabase) para staging

## 2. Setup local (primeira vez ou reset completo)

Na **raiz do repositório**:

```bash
docker compose up -d db
```

Em **`apps/web`**:

```bash
export DATABASE_URL="postgres://postgres:postgres@localhost:5432/facilcar?schema=public"
export AUTH_SECRET="$(openssl rand -base64 32)"
npm run db:push
npm run db:seed
```

Opcional no `.env`:

- `NEXT_PUBLIC_SITE_URL` — use a porta que o Next mostrar (ex.: `http://localhost:3000` ou `3001` se 3000 estiver ocupada)
- `NEXT_PUBLIC_WHATSAPP_NUMBER` — alinhado ao WhatsApp em Configurações (seed usa placeholder)

Subir o app:

```bash
npm run dev
```

**Admin (após seed):**

| Campo   | Valor              |
|---------|--------------------|
| E-mail  | `admin@facilcar.demo` |
| Senha   | `ChangeMe123!`     |

> Rodar `npm run db:seed` de novo **atualiza** `SiteSettings` e posts/páginas seedados; **não recria** veículos já existentes (mesmos slugs). Para estoque “zerado”, apague o volume Docker do Postgres ou drope o schema e rode `db:push` + `db:seed` de novo.

## 3. Validação local “como produção”

```bash
export DATABASE_URL="postgres://postgres:postgres@localhost:5432/facilcar?schema=public"
export AUTH_SECRET="$(openssl rand -base64 32)"
npm run build && npm run start
```

Smoke mínimo:

| Verificação | Esperado |
|-------------|----------|
| `GET /` | 200, home FácilCar |
| `GET /estoque` | 200, filtros |
| `GET /api/health` | 200 + `"database":"connected"` (503 se Postgres off) |
| `GET /admin` sem cookie | redirect login |
| Login admin | dashboard |
| Formulário contato/financiamento/venda | sucesso + lead no admin |

Checklist estendido: [QA_CHECKLIST.md](./QA_CHECKLIST.md).

## 4. Staging (Vercel)

1. Projeto com **Root Directory** = `apps/web`.
2. Variáveis obrigatórias: `DATABASE_URL`, `AUTH_SECRET`, `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_WHATSAPP_NUMBER`.
3. Após o primeiro deploy com banco vazio, **uma vez**:

```bash
cd apps/web
export DATABASE_URL="<url produção>"
npx prisma db push
npm run db:seed
```

4. Smoke na URL pública (mesmo roteiro do item 3).

Deploy detalhado: [DEPLOY.md](./DEPLOY.md).

## 5. Ajustes manuais antes da apresentação

1. **Admin → Configurações**: nome, WhatsApp real, e-mail, telefone, endereço, redes, hero, rodapé, SEO.
2. **Veículos em destaque**: marcar “Destaque” nos 3–4 carros que serão mostrados na home.
3. **Imagens**: URLs válidas (seed usa Picsum por padrão; troque por fotos reais se quiser).
4. **Leads de demonstração**: envie 1–2 formulários (contato + interesse em veículo) para o painel não abrir vazio.
5. **Páginas institucionais**: revisar textos; **não alterar slugs** das rotas fixas (bloqueado no admin para as páginas mapeadas).
6. **Blog**: opcional — ajustar capas (`coverImageUrl`) no admin.

## 6. Roteiro sugerido da demo (15–20 min)

1. **Home** — hero, busca, destaques, números, depoimentos, CTA.
2. **Estoque** — filtros (marca, preço, ano, combustível, câmbio).
3. **Detalhe do veículo** — galeria, ficha, confiança, WhatsApp, financiar, formulário de interesse.
4. **Lead ao vivo** — enviar formulário → **Admin → Leads** mostrar registro.
5. **Admin** — editar um veículo / hero em Configurações (opcional).
6. **Encerramento** — financiamento, consignação, integrações futuras (CRM, upload R2, etc.).

## 7. Troubleshooting

| Sintoma | Ação |
|---------|------|
| Erro Prisma / DB | Conferir `DATABASE_URL`; Postgres rodando (`docker ps`); `/api/health` |
| Login admin falha | `AUTH_SECRET` definido e estável; limpar cookies; usuário `admin@facilcar.demo` |
| Porta 3000 ocupada | Usar URL com a porta que o Next imprimir |
| Imagens quebradas | URLs acessíveis; Picsum exige rede; trocar por URLs próprias |
| Staging 500 | Logs Vercel; `db push` + `seed` no banco correto |
| Build / lockfile | Instalar em `apps/web`; ver nota em DEPLOY sobre monorepo |

## 8. Integrações opcionais

- **Resend**: e-mail em novo lead (sem config, lead só no banco).
- **R2 / S3**: presign para upload (sem config, 501 no endpoint).
- **PostHog / Sentry**: conforme `.env.example`.

---

**Referências rápidas:** [HANDOFF.md](../../HANDOFF.md) · [DEPLOY.md](./DEPLOY.md) · [QA_CHECKLIST.md](./QA_CHECKLIST.md)
