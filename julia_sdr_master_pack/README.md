# Júlia SDR — Master Project Pack

Pacote mestre de requisitos, arquitetura, regras de negócio, políticas conversacionais e plano de implementação do SDR Júlia para a FacilCar.

## Objetivo deste pacote
Este material deve ser considerado a base de trabalho para agentes de IA no CursorIDE antes de qualquer implementação relevante.

A prioridade é reduzir ambiguidade, impedir que agentes inventem regras comerciais e preservar as decisões confirmadas via HITL.

## Ordem de precedência documental
1. `docs/03_BUSINESS_PLAYBOOK.md`
2. `docs/04_CONVERSATION_POLICY.md`
3. `docs/01_PRD.md`
4. `docs/05_DOMAIN_MODEL.md`
5. `docs/06_STATE_MACHINE.md`
6. `docs/07_DATA_CONTRACTS.md`
7. `docs/08_INTEGRATIONS.md`
8. `docs/09_ARCHITECTURE.md`
9. `docs/11_SECURITY_PRIVACY.md`
10. `docs/12_TEST_STRATEGY.md`
11. `docs/14_AGENT_CONTRACT.md`

Em caso de conflito:
- regras confirmadas por HITL vencem comportamento herdado do n8n;
- tabelas oficiais do banco vencem copy, prompt ou inferência;
- ausência de dado nunca equivale a `false`;
- código determinístico é fonte de verdade para estado e transições;
- LLM interpreta e redige, mas não governa o estado do negócio.

## Escopo do MVP
O MVP deve qualificar e encaminhar oportunidades de compra, troca, venda, consignação e refinanciamento.

Tools relevantes: consultar estoque, enviar fotos, informar localização, registrar lead, registrar interesse em visita, receber/processar documentos, notificar vendedor e handoff.

## Ambiente esperado
- desenvolvimento local em Docker/Colima;
- Supabase local reduzido para testes;
- Supabase staging separado;
- Supabase produção existente;
- Evolution API local para smoke tests;
- OpenAI externa;
- produção provável em VPS Hostinger;
- app web existente continua na Vercel.
