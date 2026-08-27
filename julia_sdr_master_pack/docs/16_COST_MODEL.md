# 16 — Cost Model

## Teto
R$ 500/mês incremental total.

## Controle
- fast path sem LLM quando possível;
- structured extraction com modelo econômico;
- modelo maior só em ambiguidade;
- não reenviar histórico inteiro;
- resumo acumulado;
- cache de conhecimento;
- embeddings sob demanda;
- Vision apenas para mídia/documentos;
- respostas curtas;
- evitar cadeias longas de chamadas LLM.

## Prioridade
Correção comercial > naturalidade > latência > custo, desde que custo fique no teto e resposta permaneça em poucos segundos na maioria dos casos.
