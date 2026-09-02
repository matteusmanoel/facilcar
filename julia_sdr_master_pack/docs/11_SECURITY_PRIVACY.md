# 11 — Security & Privacy

## Documentos
Originais persistidos em bucket privado. Admin pode visualizar. Vendedor vê dados extraídos necessários, não os originais. Worker acessa apenas durante processamento.

## Retenção
Negócio `WON`: documentos permanecem permanentemente para eventuais tratativas jurídicas. Demais oportunidades: documentos e conteúdo conversacional sensível expiram após 180 dias; métricas mínimas agregadas/anônimas podem permanecer.

## CPF/CNPJ
Mascarar por padrão na UI. Exibição completa apenas em contexto administrativo específico.

## Coleta
Explicar motivo antes de solicitar dado sensível. Recusa deve ser respeitada e não bloquear handoff se a oportunidade for acionável.

## RLS
A investigação atual apontou RLS desligado em tabelas do schema `facilcar`. Antes do go-live, investigar exposição via Data API e reduzir superfície de `service_role`.

## Secrets e logs
Nunca commitados/expostos ao browser. Mascarar CPF, renda, endereço, documentos, tokens e URLs assinadas nos logs.
