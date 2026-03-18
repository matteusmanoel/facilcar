# Infrastructure and Deploy

## Objetivo
Ter um ambiente de MVP com deploy rápido, baixo custo e baixa fricção operacional.

## Infra recomendada
### Aplicação
- Vercel

### Banco
- Neon Postgres ou Supabase Postgres

### Storage de imagens
- Cloudflare R2, AWS S3 ou UploadThing

### DNS / borda
- Cloudflare

### E-mail
- Resend

### Monitoramento
- Sentry

### Analytics
- PostHog ou Google Analytics 4

## Ambientes
### Local
- desenvolvimento diário
- banco local ou remoto dedicado de dev

### Preview
- deploy automático por branch/PR

### Production
- domínio público para demo

## Variáveis de ambiente mínimas
- DATABASE_URL
- NEXTAUTH_SECRET / AUTH_SECRET
- NEXTAUTH_URL / AUTH_URL
- RESEND_API_KEY
- RESEND_FROM_EMAIL
- STORAGE_BUCKET_NAME
- STORAGE_ACCESS_KEY
- STORAGE_SECRET_KEY
- STORAGE_ENDPOINT
- STORAGE_PUBLIC_URL
- CAPTCHA_SITE_KEY
- CAPTCHA_SECRET_KEY
- NEXT_PUBLIC_SITE_URL
- NEXT_PUBLIC_WHATSAPP_NUMBER
- NEXT_PUBLIC_GA_ID ou NEXT_PUBLIC_POSTHOG_KEY
- SENTRY_DSN

## Pipeline de deploy
1. push para repositório
2. preview deploy automático
3. migrations aplicadas
4. seed opcional em ambiente de demo
5. smoke test manual
6. publish em produção/demo

## Setup sugerido
### Banco
- criar projeto Postgres
- aplicar migrations
- criar usuário admin inicial

### Storage
- criar bucket público controlado
- política de acesso restrita a uploads autenticados

### Domínio
- usar subdomínio de demo ou staging
- ex.: `demo.nome-do-cliente.com`

## Estratégia de custo
MVP deve caber em stack de baixo custo. Evitar:
- Kubernetes
- microserviços
- Redis obrigatório
- fila complexa
- infraestrutura self-hosted desnecessária

## Backup e retenção
- confiar inicialmente no backup gerenciado do provider do banco
- export simples da base antes de marcos importantes

## CI/CD
Mínimo viável:
- lint
- typecheck
- build
- migrate deploy em produção com cuidado

## Riscos operacionais
- uploads grandes demais
- spam em formulários
- má configuração de domínio/SMTP
- uso excessivo de scripts client-side afetando performance
