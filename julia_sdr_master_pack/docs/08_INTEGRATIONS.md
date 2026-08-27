# 08 — Integrations

## Supabase
Produção: projeto existente e fonte de verdade. Staging: projeto separado, catálogo público replicável, sem dados pessoais reais. Local: Supabase CLI reduzido.

## Evolution API
Webhook, envio de mensagens, mídia e detecção `fromMe`. Container local obrigatório para smoke tests.

Número de teste reservado: `5545988432998`.

## OpenAI
Permitida para entendimento, extração estruturada, Vision, documentos sensíveis, áudio, resposta e embeddings quando necessário. Não governa estado canônico.

## Supabase Storage
Bucket privado para CNH, CRLV, holerite, comprovante de residência e demais arquivos.

## Vehicle
Somente `PUBLISHED` é estoque disponível. `priceCash` é preço principal. Outros campos apenas quando preenchidos.

## Painel web
Permanece na Vercel. Antes de consolidar monorepo, investigar impacto de `apps/sdr` no build/deploy.

## Notificações
Central no painel, badge, toast e som opcional.
