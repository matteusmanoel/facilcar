# 05 — Domain Model

## Fonte de verdade existente
Reutilizar `Customer`, `Lead`, `FinancingRequest`, `SellRequest`, `Vehicle`, `VehicleImage`, `User` e `SiteSettings`. Não criar CRM paralelo.

## Customer
Identidade principal: telefone normalizado. Nome de perfil é hipótese até confirmação explícita.

## Lead
Estados: `NEW`, `QUALIFIED`, `WON`, `LOST`. Um Customer pode ter vários Leads.

## Regra de criação
Primeira mensagem cria Thread e upsert de Customer. Saudação isolada não cria Lead. Lead nasce quando há intenção comercial identificável.

## Um negócio, um Lead
Compra + troca + financiamento = uma oportunidade. Negócios realmente independentes podem gerar Leads distintos.

## Conversation / Thread
Entidade aditiva recomendada: phone, status bot/humano, idioma, resumo, last_message_at, lead IDs ativos, handoff state e timestamps.

## Message
Entidade aditiva: provider_message_id, direction, content_type, text, media reference, from_me, language, created_at, processed_at e metadata.

## VisitInterest
MVP: interesse, data/período opcional e observação, sem confirmação automática.

## Temperatura
HOT/WARM/COLD como auxílio visual, nunca condição de handoff.

## Estado humano
Pertence ao Thread. Se qualquer oportunidade daquele chat entra em atendimento humano, a Júlia silencia toda a conversa.
