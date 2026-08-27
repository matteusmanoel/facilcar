# Prompt Contract

## LLM pode
Classificar intenção, extrair fatos, detectar sinais, resumir, compor resposta, adaptar idioma e explicar conhecimento recuperado.

## LLM não pode
Decidir sozinho handoff final, alterar stage canônico, inventar estoque/atributos/preço/aprovação/avaliação, apagar estado ou criar política.

## Structured output
Preferir schema validado por Pydantic.

## Contexto
Estado estruturado + resumo acumulado + últimas mensagens relevantes + knowledge context quando necessário. Não enviar histórico integral sem necessidade.
