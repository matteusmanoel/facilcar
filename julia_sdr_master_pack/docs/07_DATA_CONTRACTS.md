# 07 — Data Contracts

## Filosofia
O LLM retorna somente fatos detectados no turno. Nunca o estado completo como autoridade.

## TurnFacts
```json
{
  "intent": "trade",
  "language": "pt-BR",
  "facts": {},
  "signals": {
    "explicit_handoff": false,
    "explicit_offer": false,
    "visit_intent": false,
    "high_purchase_intent": false
  },
  "confidence": {}
}
```

## Merge
`new_state = deterministic_merge(previous_state, turn_facts)`

Regras: omissão não apaga dado anterior; correção explícita pode sobrescrever; conflito crítico exige confirmação; `unknown` não é `false`.

## Allowed actions
`ask_info`, `show_offers`, `send_photos`, `send_location`, `register_visit_interest`, `handoff_vendor`, `smalltalk`, `no_reply`.

## Tool contracts
Input/output tipados, timeout, retry, idempotency key, correlation id, erro classificado e sem payload raw direto ao LLM.
