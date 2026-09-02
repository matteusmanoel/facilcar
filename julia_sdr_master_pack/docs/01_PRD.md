# 01 — Product Requirements Document

## Objetivo funcional
Permitir que clientes iniciem atendimento via WhatsApp e sejam conduzidos até qualificação suficiente, criação/atualização da oportunidade no CRM, handoff automático e continuidade humana pelo mesmo canal.

## Tipos de negócio suportados

### Compra
Coletar preferencialmente: modelo/versão ou categoria desejada, faixa de valor, forma de pagamento, intenção/prazo de compra e preferência novo/seminovo/usado quando aplicável.

### Compra com financiamento
Coletar: veículo/perfil desejado, valor aproximado, entrada disponível, renda aproximada quando houver solicitação de simulação, prazo para compra e dados pessoais conforme contexto e conforto. Prazo/parcelas são nice-to-have e não bloqueiam qualificação.

### Troca
Coletar: veículo desejado, faixa de valor, veículo entregue, marca/modelo, ano, versão se souber, km, estado geral, situação de financiamento/alienação e expectativa financeira se houver.

### Venda
Coletar: marca/modelo, ano, versão se conhecida, km, estado geral, cidade/localização, quitado/financiado, valor pretendido e prazo/intenção.

### Consignação
Coletar: veículo, ano, versão, km, estado geral, localização, valor desejado, flexibilidade, quitação, prazo/intenção e se aceita deixar o veículo na loja.

### Refinanciamento
Coletar: marca/modelo, ano, valor aproximado do veículo, valor que deseja levantar, situação do financiamento, saldo devedor quando aplicável, parcelas restantes aproximadas se conhecidas, renda aproximada e prazo quando fizer sentido.

## Triagem mínima
A triagem é suficiente quando o vendedor consegue continuar a negociação sem voltar ao zero. A avaliação combina hard blockers mínimos e actionability semântica.

## Handoff antecipado
Ocorre diante de pedido explícito de vendedor, proposta comercial explícita, intenção forte de fechar, visita imediata ou contexto já comercialmente acionável.

## Tools do MVP
- consulta de estoque;
- envio de fotos;
- localização;
- registro de Lead;
- upload/processamento de documentos;
- notificação ao vendedor;
- handoff;
- registro simples de interesse em visita.

## Fora do MVP
Agenda transacional completa, follow-up proativo, inbox WhatsApp completo no painel, simulador financeiro próprio, integração bancária, cálculo CET, avaliação automática do veículo, knowledge-base editável via UI e analytics sofisticado.

## Mensagens
- preferir 1–3 bolhas curtas por turno;
- uma pergunta por vez quando possível;
- não disparar questionários.

## Idiomas
Critério formal de aceite: PT-BR e espanhol.

## Critério de pronto
WhatsApp → ingestão → compreensão → persistência → qualificação → tools → documentos → Lead → `QUALIFIED` → resumo → notificação → handoff → silêncio da Júlia, validado nos fluxos de compra, troca, venda, consignação e refinanciamento.
