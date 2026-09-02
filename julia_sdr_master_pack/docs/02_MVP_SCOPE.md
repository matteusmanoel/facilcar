# 02 — MVP Scope

## In Scope
### Conversação
Texto, áudio, imagem, documento, PT-BR, espanhol e respostas em bolhas curtas.

### Domínio
Compra, compra financiada, troca, venda, consignação e refinanciamento.

### CRM
Reutilizar `Customer`, `Lead`, `FinancingRequest`, `SellRequest`; adicionar Conversation/Thread, Message e estrutura simples de interesse de visita/eventos.

### Painel
Fila de oportunidades, central de notificações, `NEW/QUALIFIED/WON/LOST`, temperatura, tipo de negócio, resumo da Júlia, dados coletados, interesse de visita, botão Assumir, indicador de nova oportunidade e documentos originais apenas para Admin.

### Integrações
Evolution API, Supabase, OpenAI, Supabase Storage e app web existente.

## Out of Scope
Agenda completa, follow-up automático, campanhas outbound, inbox WhatsApp interno, múltiplos vendedores com roteamento sofisticado, cálculo de financiamento, integração bancária, avaliação automática, knowledge CMS, Kubernetes, autoscaling e BI completo.
