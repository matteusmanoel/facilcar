# 06 — State Machine

## Princípio
Estado é determinístico. LLM não controla lifecycle.

```mermaid
stateDiagram-v2
    [*] --> BOT_ACTIVE
    BOT_ACTIVE --> QUALIFYING: intenção comercial
    QUALIFYING --> READY_FOR_HANDOFF: triagem acionável
    QUALIFYING --> READY_FOR_HANDOFF: pedido vendedor/proposta/alta intenção
    READY_FOR_HANDOFF --> HANDOFF_SENT: confirmação enviada
    HANDOFF_SENT --> HUMAN_ACTIVE: vendedor assume ou fromMe humano
    HUMAN_ACTIVE --> HUMAN_CLOSED: atendimento encerrado
    HUMAN_CLOSED --> BOT_ACTIVE: nova intenção futura
```

## Lead
```mermaid
stateDiagram-v2
    [*] --> NEW
    NEW --> QUALIFIED: triagem/handoff
    QUALIFIED --> WON: vendedor
    QUALIFIED --> LOST: vendedor
```

## Regras
- `HANDOFF_SENT` permite exatamente uma mensagem automática.
- `HUMAN_ACTIVE` proíbe IA.
- Conversation incompleta e Lead NEW não expiram automaticamente no MVP.
