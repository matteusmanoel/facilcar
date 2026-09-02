# 12 — Test Strategy

## Filosofia
Testar comportamento antes de implementação.

## Unitários obrigatórios
Merge de estado, normalização de JID/telefone, regras de triagem, handoff, unknown vs false, intents simples, acesso a estoque, retenção e permissões.

## Conversation scenarios
Cada cenário contém estado inicial, mensagens, fatos esperados, perguntas proibidas, ação e handoff esperado.

## Integration
Smoke tests de Evolution, Supabase, Storage e OpenAI.

## E2E mínimos
Compra, financiamento, troca, venda, consignação, refinanciamento, documento, handoff e `fromMe` humano.

## Invariantes
1. Campo conhecido não desaparece por omissão do LLM.
2. Ausência não vira `false`.
3. Dados extraídos com confiança não são perguntados de novo.
4. Conflitos críticos pedem confirmação.
5. Handoff bloqueia IA.
6. Vehicle não PUBLISHED nunca é ofertado.
7. Campo ausente nunca é inventado.
8. Júlia não avalia financeiramente veículo.
9. Júlia não promete aprovação.
10. Proposta explícita gera handoff.
11. Pedido de vendedor gera handoff.
12. Recusa de documento não entra em loop.
13. Saudação não cria Lead.
14. Intenção comercial cria Lead NEW.
15. Triagem acionável cria QUALIFIED.

## Regressão
Todo bug conversacional reproduzível vira cenário permanente.
