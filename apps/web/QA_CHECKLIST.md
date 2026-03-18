# QA rápido (MVP)

**Pré-requisitos:** Postgres (Docker ou remoto), `db:push` + `db:seed`, `AUTH_SECRET` definido.

## Público

- [ ] Home (`/`) com destaques e links
- [ ] `/estoque` lista, filtros e paginação (ordenar + **Filtrar**)
- [ ] `/estoque/[slug]` ficha, galeria, interesse no veículo
- [ ] `/contato`, `/financiamento`, `/vender-seu-veiculo` — submit → sucesso
- [ ] Institucionais: `/quem-somos`, `/politica-de-privacidade`, `/termos-de-uso`, `/nosso-estoque`, `/trabalhe-conosco`
- [ ] `/blog` e `/blog/[slug]`

## Admin

- [ ] `/admin/login` → **200**, formulário visível
- [ ] Sem sessão: `/admin` → redirect para `/admin/login?callbackUrl=/admin`
- [ ] Login: `admin@autodealerdemo.com` / `ChangeMe123!` → dashboard
- [ ] `/admin/veiculos`, novo, editar
- [ ] `/admin/leads` e detalhe + status
- [ ] `/admin/paginas`, `/admin/blog` — edição
- [ ] `/admin/configuracoes`
- [ ] **Sair** → volta para `/admin/login`

## Integrações opcionais

- [ ] Resend: lead cria e-mail (envs preenchidas)
- [ ] R2: presign autenticado (admin logado + `STORAGE_*`)
- [ ] PostHog: sem env, app não quebra

## Build

- [ ] `npm run lint` (warnings de `<img>` aceitáveis)
- [ ] `npm run typecheck`
- [ ] `npm run build` sem erros
