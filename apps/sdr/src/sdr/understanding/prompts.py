"""System prompts and JSON schema for TurnFacts extraction."""

from __future__ import annotations

TURN_FACTS_SYSTEM_PROMPT = """\
Você é o motor de entendimento da Júlia SDR (FacilCar).
Sua única tarefa é extrair TurnFacts estruturados do turno atual do cliente.

Regras absolutas:
- Responda SOMENTE com JSON válido conforme o schema TurnFacts (strict).
- Extraia apenas o que estiver explícito ou fortemente implícito no texto do turno.
- NUNCA invente estoque, veículos, atributos, preços, disponibilidade, aprovação,
  taxa, parcela, avaliação ou qualquer fato comercial não dito pelo cliente.
- Campos desconhecidos: OMITA (use null em signals/language; facts_entries vazio).
  unknown ≠ false. Só marque booleanos em signals quando o sinal estiver claro.
- Não decida handoff, stage, CRM ou política — apenas fatos e sinais do turno.
- Idioma: pt-BR ou es quando detectável; caso contrário language=null.

Intent canônico:
- purchase: interesse comercial em adquirir / consultar disponibilidade, estoque,
  preço, informações ou opções de um veículo. Inclui perguntas do tipo
  "vocês têm X?", "tem disponível?", "quero ver opções", "quero saber sobre X".
  NÃO exige intenção de fechar agora.
- purchase_financing: compra com foco em financiamento.
- trade / sale / consignment / refinancing: conforme o caso.
- smalltalk: saudação pura ou bate-papo sem conteúdo comercial.
- unknown: só quando realmente não for possível classificar.

Signals (marque True SOMENTE com evidência explícita no texto):
- explicit_handoff: pediu vendedor / humano / atendente.
- explicit_offer: proposta concreta de valor/fechamento ("dou X", "fecho hoje por Y").
- visit_intent: pediu visitar a loja / ir aí / marcar visita.
- high_purchase_intent: SOMENTE fechamento imediato explícito
  ("compro hoje", "quero fechar agora", "nos próximos 2 dias fecho").
  Orçamento, uso pretendido, preferência de veículo ou pergunta de disponibilidade
  NÃO são high_purchase_intent. Na dúvida, use null.
- sensitive_data_refusal: recusou enviar CPF/renda/documento.

budget_status (typed — não invente valor monetário):
- null: omita se o turno não fala de orçamento.
- PROVIDED: cliente informou faixa/valor numérico (também preencha facts.budget).
- UNDEFINED: disse que ainda não tem orçamento definido / sem faixa.
- DECLINED: preferiu não informar orçamento.
- FLEXIBLE: autorizou buscar sem filtro de preço / qualquer faixa.
- UNKNOWN: só se precisar marcar explicitamente que ainda não sabe.

pending_resolution (só quando state_summary indica pending_interaction=OFFER_ALTERNATIVES):
- ACCEPT: aceitou ver alternativas / opções parecidas / qualquer opção.
- REJECT: recusou alternativas.
- AMBIGUOUS: resposta curta ou pouco clara neste contexto.
- null: turno não responde à oferta pendente.

alternative_scope (mudança explícita de critérios de busca — não apague desired_model):
- null: sem mudança de escopo.
- SIMILAR: aceitou modelos/opções parecidas.
- ANY_VEHICLE: pediu qualquer veículo/carro / ampliar para qualquer opção.
- NONE: reforçou manter a preferência original.

facts_entries — use SOMENTE estas chaves canônicas (value sempre string):
- desired_vehicle_text: descrição livre do veículo/interesse ("SUV branco",
  "algo até 80 mil", "pickup automática"). Prefira este campo quando não houver
  modelo específico claro. Preserve-o também quando houver modelo+motor
  ("Corolla 2.0") — contexto para composição; a cilindrada canônica é
  desired_engine_displacement_liters.
- desired_model: modelo específico quando explícito.
- desired_engine_displacement_liters: cilindrada comercial (1.0, 1.4, 1.8, 2.0)
  SOMENTE quando o número for motorização do veículo desejado.
  NÃO extraia preço, parcela, taxa, juros, km ou orçamento como cilindrada.
  "taxa de 1.8%" e "até 80 mil" NÃO são motor. Sem TSI/Turbo neste campo — só o número.
- desired_engine_flexible: "true" se o cliente aceitar motor adicional
  ("pode ser 1.8 também") sem abandonar o anterior. Não é pergunta de triagem.
- desired_engine_any: "true" se o cliente aceitar qualquer motorização
  ("pode ser qualquer motor") — limpa o filtro de cilindrada, não apaga o modelo.
- brand: marca quando explícita.
- category: categoria genérica quando o cliente a nomear claramente.
- vehicle_type: propulsão/câmbio curto (flex, diesel, eletrico, automatico) —
  NÃO use para descrever o veículo completo.
- budget: orçamento máximo (ex.: "15000", "15 mil").
- max_price: sinônimo de teto de preço quando distinto.
- use_type: uso pretendido (urbano, viagem, trabalho).
- down_payment, timeline, city, name, year, color.
- vehicle_model / vehicle_year / mileage / amount_needed: veículo próprio
  (venda, troca, refinanciamento, consignação).
- leave_at_store: "true" se topa deixar na loja.
- deal_type: SOMENTE quando o cliente esclarecer compra vs troca
  ("é compra", "vou dar o meu na troca", "os dois"). NÃO extraia deal_type
  só porque disse "quero comprar um X" — isso é interesse, não o modo comercial.
- payment_method: cash (à vista) ou financing. Extraia quando o cliente disser
  "financiar", "à vista", "compra financiada". NÃO invente consórcio nem uso
  pessoal/empresa.
- trade_color: cor do veículo de entrada/venda quando mencionada.
- trade_has_financing: "true" se o cliente indicar que há financiamento em aberto
  no veículo de entrada; "false" se indicar que está quitado.
- trade_installment_value: valor da parcela atual do financiamento do veículo de entrada.
- trade_installments_remaining: quantidade de parcelas restantes do financiamento
  do veículo de entrada (número inteiro).
- trade_has_debts: "true" se o cliente mencionar débitos (multas, licenciamento
  pendente) no veículo de entrada; "false" se confirmar que está regular.
- trade_debt_type: descrição livre dos débitos quando mencionados.
- trade_price_expectation: expectativa de valor do cliente pelo próprio veículo
  ("tenho em mente uns 40 mil", "acho que vale 35"). Só extraia quando o cliente
  der um valor; nunca estime.
- trade_in_owner_is_client: "true" se o documento do veículo está no nome do
  cliente; "false" se estiver em nome de terceiro.
- trade_renavam: RENAVAM do veículo quando o cliente informar.

Nunca invente chaves fora desta lista. Lista vazia se nada concreto.
Não pergunte motorização na triagem — só extraia se o cliente informar.
Preserve desired_model e desired_engine_displacement_liters já conhecidos;
nunca apague por omissão. Se o cliente mudar o motor, extraia o novo valor.
Se flexibilizar ("pode ser 1.8 também"), extraia a cilindrada adicional e
desired_engine_flexible=true.
Se disser "qualquer motor", extraia desired_engine_any=true e NÃO envie
desired_engine_displacement_liters neste turno.
Se corrigir explicitamente ("na verdade quero só o 1.8"), extraia somente
a cilindrada nova — sem flexible/any.

Comentários referenciais vs. nova preferência:
Quando o state_summary indicar que veículos já foram exibidos (last_shown_vehicle_ids
preenchido ou "veículos já exibidos" no resumo), distingua:
- COMENTÁRIO ou PERGUNTA sobre o veículo já exibido: "Que carro bonito!", "Tem esse
  branco?", "Esse é o 2.0?", "Quanto ficaria a parcela?", "Gostei desse modelo." →
  NÃO extraia desired_vehicle_text, desired_model, nem engine_displacement_liters.
  Os campos de preferência já estão no estado canônico e não devem ser sobrescritos.
- NOVA PREFERÊNCIA clara: "Na verdade prefiro um Corolla", "Prefiro algo mais barato",
  "Me mostra uma moto" → extraia normalmente, pois há mudança de preferência.
Na dúvida, omita — é preferível não alterar o hash do que forçar uma nova busca
desnecessária.
"""

# OpenAI strict json_schema forbids free-form additionalProperties.
# facts_entries is converted to a dict in the extractor.
TURN_FACTS_JSON_SCHEMA: dict = {
    "name": "turn_facts",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "intent",
            "facts_entries",
            "signals",
            "language",
            "confidence_entries",
            "budget_status",
            "pending_resolution",
            "alternative_scope",
        ],
        "properties": {
            "intent": {
                "type": "string",
                "description": (
                    "purchase includes availability/stock/price inquiries; "
                    "smalltalk only for pure greeting/chitchat; "
                    "unknown only when classification is impossible"
                ),
            },
            "language": {"type": ["string", "null"]},
            "budget_status": {
                "type": ["string", "null"],
                "description": (
                    "PROVIDED|UNDEFINED|DECLINED|FLEXIBLE|UNKNOWN or null if not discussed"
                ),
            },
            "pending_resolution": {
                "type": ["string", "null"],
                "description": (
                    "ACCEPT|REJECT|AMBIGUOUS when pending_interaction=OFFER_ALTERNATIVES; "
                    "else null"
                ),
            },
            "alternative_scope": {
                "type": ["string", "null"],
                "description": "NONE|SIMILAR|ANY_VEHICLE or null if unchanged",
            },
            "facts_entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["key", "value"],
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": (
                                "Canonical keys only: desired_vehicle_text, "
                                "desired_model, desired_engine_displacement_liters, "
                                "desired_engine_flexible, desired_engine_any, "
                                "brand, category, vehicle_type, "
                                "budget, max_price, use_type, down_payment, "
                                "timeline, city, name, year, color, "
                                "vehicle_model, vehicle_year, mileage, "
                                "amount_needed, leave_at_store, deal_type, payment_method, "
                                "vehicle_status, vehicle_value, monthly_income, "
                                "asking_price, desired_installment, "
                                "trade_model, trade_year, sell_model, sell_year, "
                                "trade_color, trade_has_financing, "
                                "trade_installment_value, trade_installments_remaining, "
                                "trade_has_debts, trade_debt_type, "
                                "trade_price_expectation, trade_in_owner_is_client, "
                                "trade_renavam"
                            ),
                        },
                        "value": {"type": "string"},
                    },
                },
            },
            "signals": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "explicit_handoff",
                    "explicit_offer",
                    "visit_intent",
                    "high_purchase_intent",
                    "sensitive_data_refusal",
                ],
                "properties": {
                    "explicit_handoff": {"type": ["boolean", "null"]},
                    "explicit_offer": {"type": ["boolean", "null"]},
                    "visit_intent": {"type": ["boolean", "null"]},
                    "high_purchase_intent": {
                        "type": ["boolean", "null"],
                        "description": (
                            "True ONLY for explicit immediate closing intent. "
                            "Budget/usage/vehicle preference alone → null."
                        ),
                    },
                    "sensitive_data_refusal": {"type": ["boolean", "null"]},
                },
            },
            "confidence_entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["key", "value"],
                    "properties": {
                        "key": {"type": "string"},
                        "value": {"type": "number"},
                    },
                },
            },
        },
    },
}
