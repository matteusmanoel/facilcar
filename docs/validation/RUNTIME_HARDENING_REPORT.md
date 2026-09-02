# Júlia SDR — Runtime Hardening Report (Round 4)

> Builds on Round 3. Primary fix: inventory tool failure must never become stock absence.

## Exit criterion (accepted)

This sequence is now impossible:

```text
inventory_search error → "não temos no estoque"
```

Accepted live sequence:

```text
ToolResults: outcome=FAILED_RETRYABLE error_code=no_db_pool
Directive: inventory_outcome=FAILED_RETRYABLE
Validator: PASS
Outbound:
  > Não consegui consultar nosso estoque agora.
  > Posso tentar novamente ou encaminhar seu interesse para a equipe.
```

## Round 3 preserved

- Pure-greeting fast path
- Live commercial understanding (`purchase` + canonical facts)
- Monetary normalization
- False high-purchase gated
- Inventory-first decision
- Visible `SDR_TRACE`

## 1. Typed inventory outcomes

`InventoryOutcome` in `domain/types.py` + policy in `domain/inventory_outcome.py`:

| Outcome | Meaning |
|---------|---------|
| `SUCCESS_FOUND` | Matching PUBLISHED vehicles found |
| `SUCCESS_EMPTY` | Query succeeded; zero current matches |
| `FAILED_RETRYABLE` | Temporary failure (`no_db_pool`, timeout, connection) |
| `FAILED_TERMINAL` | Malformed / unknown tool / hard failure |
| `NOT_EXECUTED` | Inventory not run this turn |

ToolResults carry sanitized fields: `outcome`, `count`, `vehicles`/`alternatives`, `failure_category`, `retryable`, `error_code` (trace only).

## 2. Truth semantics

- Failure → must not claim absence
- Empty → may claim no match in *current published stock*; must not claim store policy
- Composer for `SHOW_OFFERS` uses deterministic `compose_inventory_response` driven by directive outcome
- Validator rejects absence claims on failure and permanent policy claims on empty; falls back safely

## 3. ResponseDirective inventory policy

New fields: `inventory_outcome`, `claims_allowed`, `claims_forbidden`, `inventory_count`, `inventory_alternatives`.

## 4. Deterministic fallbacks

Failure: “Não consegui consultar nosso estoque agora…”  
Empty: “Não encontrei uma opção com esse perfil no estoque atual…”

Meanings remain separate.

## 5. Validator

`validate_inventory_policy` enforces claim rules; returns structured `{pass, violations, fallback_used}`.

## 6. Search key updates

Only `SUCCESS_FOUND` / `SUCCESS_EMPTY` update `last_inventory_search_key` (+ `last_inventory_outcome`). Failures do not.

## 7. Handoff signal gating (all irreversible paths)

`gate_handoff_signals` now requires deterministic inbound evidence for:

- `explicit_handoff`
- `explicit_offer`
- `visit_intent`
- `high_purchase_intent`

LLM false positives without text evidence are stripped.

## 8. SUCCESS_EMPTY vs handoff

Inventory-first prevents same-turn handoff when a search is still needed.  
`SUCCESS_EMPTY` is answered in the `SHOW_OFFERS` turn (current-stock miss + alternatives question).  
Subsequent-turn `triage_actionable` handoff remains intentional when the lead is seller-actionable — it is **not** triggered by tool failure.

## 9. Validation evidence

```bash
# Python
pytest tests/ -q
→ 178 passed

# Live without DB pool (truthful failure response)
SDR_TRACE=true LIVE_LLM=1 python -m sdr.replay unseen_scooter_scenario
→ ✅ ALL ASSERTIONS PASSED
→ outbound: consultation failure, NOT "não temos"

SDR_TRACE=true LIVE_LLM=1 python -m sdr.replay smoke_replay
→ ✅ ALL ASSERTIONS PASSED
→ same truthful failure phrasing

# TypeScript
npx tsc --noEmit → clean
```

## 10. Remaining limitations

- Live replay still has no DB pool — `SUCCESS_FOUND` / live PUBLISHED ranking exercised via unit/integration doubles (`test_inventory_truth`, `test_inventory_ranking`), not against production DB in this run.
- Accumulated conversation summary still not generated.
- End-to-end Evolution audio remains mock-covered.

## Status

**Round 4 inventory-truth contract: ACCEPTED** for the tool-error → customer-response path.  
Round 3 semantic contracts preserved.
