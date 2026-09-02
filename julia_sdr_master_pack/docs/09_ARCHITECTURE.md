# 09 — Architecture

## Diretriz
Não portar n8n nó por nó. Extrair regras, intents, lifecycle, tools, multimodal, RAG, handoff e safeguards.

```mermaid
flowchart LR
    W[WhatsApp / Evolution] --> A[Ingress API]
    A --> O[Conversation Orchestrator]
    O --> N[Normalizer]
    N --> M[Media Processor]
    N --> U[Understanding Engine]
    M --> U
    U --> S[State Merge]
    S --> D[Decision Engine]
    D --> K[Knowledge Router]
    K --> R[RAG]
    D --> T[Tool Router]
    R --> C[Response Composer]
    T --> C
    C --> V[Response Validator]
    V --> W
    S --> P[(Supabase/Postgres)]
    O --> E[(Redis/ephemeral)]
    M --> ST[(Supabase Storage)]
    D --> CRM[Lead/CRM]
```

## Componentes
- FastAPI para ingress/API interna.
- Worker Python para processamento.
- Redis somente para lock, idempotência, debounce e cache efêmero.
- Supabase/PostgreSQL como fonte de verdade.
- Understanding Engine produz `TurnFacts`.
- Decision Engine é determinístico.
- Response Composer usa LLM somente para linguagem.

## Temporal
Não obrigatório no MVP. Começar simples com worker Python + Redis/DB. Introduzir orquestrador durável apenas se a complexidade futura justificar.

## Concorrência
Lock por thread/telefone, um processamento ativo por thread, idempotência por provider message ID e `fromMe` humano sempre vence IA.

## Debounce
Janela configurável curta, não copiar mecanicamente wait de 7s do n8n.

## Monorepo
Preferência `apps/sdr`, pendente preflight de impacto na Vercel.
