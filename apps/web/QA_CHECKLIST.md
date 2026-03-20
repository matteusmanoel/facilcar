# QA rápido (MVP)

**Pré-requisitos:** Postgres, `db:push` + `db:seed`, **`AUTH_SECRET`** definido.

## Produção local (recomendado antes do deploy)

```bash
cd apps/web
export DATABASE_URL="postgres://postgres:postgres@localhost:5432/facilcar?schema=public"
export AUTH_SECRET="$(openssl rand -base64 32)"
npm run build && npm run start
```

- [ ] `/` e `/estoque` retornam 200
- [ ] `/admin` sem login → redirect para `/admin/login`
- [ ] Login admin → dashboard
- [ ] `GET /api/health` → 200 e `database: connected`

## Público

- [ ] Home (`/`) com destaques e links
- [ ] `/estoque` — filtros + **Filtrar**
- [ ] `/estoque/[slug]` — ficha + interesse
- [ ] `/contato`, `/financiamento`, `/vender-seu-veiculo` — submit → sucesso
- [ ] Institucionais: `/quem-somos`, `/politica-de-privacidade`, `/termos-de-uso`, `/nosso-estoque`, `/trabalhe-conosco`
- [ ] `/blog` e `/blog/[slug]`

## Admin

- [ ] `/admin/login` → **200**
- [ ] Sem sessão: `/admin` → `/admin/login?callbackUrl=...`
- [ ] Login: `admin@facilcar.demo` / `ChangeMe123!`
- [ ] `/admin/veiculos`, novo, editar
- [ ] `/admin/leads` + detalhe + status
- [ ] `/admin/paginas`, `/admin/blog`, `/admin/configuracoes`
- [ ] **Sair** → `/admin/login`

## Integrações opcionais (degradação segura)

- [ ] Sem Resend: lead grava no banco, sem e-mail
- [ ] Sem R2: presign 501; imagens por URL manual no admin
- [ ] Sem PostHog: app normal

## Build

- [ ] `npm run lint` (warnings `<img>` ok)
- [ ] `npm run typecheck`
- [ ] `npm run build`

## Pós-deploy (Vercel)

- [ ] Mesmo smoke de público + admin na URL de produção
- [ ] `db push` + `seed` já rodados no Postgres de produção
