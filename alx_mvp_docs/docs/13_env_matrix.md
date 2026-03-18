# Environment Matrix

## Local
- banco de desenvolvimento
- auth local
- storage mock ou bucket de dev
- analytics opcional

## Preview
- banco isolado ou schema isolado
- deploy automático por branch
- sem envs sensíveis desnecessárias

## Production / Demo
- domínio público
- envs reais
- observabilidade ativa

## Variáveis
| Variável | Obrigatória | Ambiente | Finalidade |
|---|---:|---|---|
| DATABASE_URL | sim | todos | conexão com Postgres |
| AUTH_SECRET | sim | todos | sessão/autenticação |
| AUTH_URL | prod/preview | preview/prod | URL base de auth |
| NEXT_PUBLIC_SITE_URL | sim | todos | URL pública do site |
| NEXT_PUBLIC_WHATSAPP_NUMBER | sim | todos | CTA WhatsApp |
| RESEND_API_KEY | opcional no início | preview/prod | e-mail |
| RESEND_FROM_EMAIL | opcional no início | preview/prod | remetente |
| STORAGE_ENDPOINT | sim se usar S3/R2 | todos | storage |
| STORAGE_BUCKET_NAME | sim se usar S3/R2 | todos | storage |
| STORAGE_ACCESS_KEY | sim se usar S3/R2 | todos | storage |
| STORAGE_SECRET_KEY | sim se usar S3/R2 | todos | storage |
| STORAGE_PUBLIC_URL | sim se usar S3/R2 | todos | URL pública das imagens |
| CAPTCHA_SITE_KEY | recomendado | preview/prod | captcha client |
| CAPTCHA_SECRET_KEY | recomendado | preview/prod | captcha server |
| NEXT_PUBLIC_GA_ID | opcional | preview/prod | analytics |
| NEXT_PUBLIC_POSTHOG_KEY | opcional | preview/prod | analytics |
| SENTRY_DSN | opcional | preview/prod | monitoramento |
