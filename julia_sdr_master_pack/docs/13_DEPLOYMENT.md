# 13 — Deployment

## Ambientes
Local: Docker/Colima + Supabase local + Evolution local + OpenAI externa.

Staging: Supabase separado, catálogo público replicado, sem dados pessoais reais.

Produção provável: VPS Hostinger para SDR/Evolution, Supabase produção existente e web na Vercel.

## VPS MVP
Docker Compose, reverse proxy, TLS, healthchecks, restart policies, logs rotacionados e backup de configuração. Kubernetes não é requisito.

## Feature flag
Se simples, implementar `JULIA_ENABLED=true/false` como kill switch global.

## Go-live gates
Gate técnico: migrations, backup, smoke, E2E, segurança básica e rollback.

Gate comercial: Milton valida roteiro representativo.

## Piloto
Começa com 100% das novas conversas no número oficial.

## Rollback
Deve ser possível desligar respostas da Júlia mantendo ingestão e preservando mensagens/estado para continuidade humana.
