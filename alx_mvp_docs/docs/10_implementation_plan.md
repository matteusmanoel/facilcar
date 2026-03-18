# Implementation Plan

## Estratégia de execução no CursorIDE
Executar em etapas, com checkpoints claros, evitando pedir “faça tudo” sem controle.

## Etapa 1 — Bootstrap
Objetivos:
- criar projeto
- instalar dependências
- configurar lint, TypeScript, Tailwind, shadcn/ui, Prisma e Auth

Saídas esperadas:
- app inicial compilando
- README técnico
- estrutura de pastas criada

## Etapa 2 — Banco e modelos
Objetivos:
- implementar Prisma schema
- gerar migrations
- criar seed inicial

Saídas esperadas:
- schema funcional
- banco inicial populável

## Etapa 3 — UI base
Objetivos:
- layouts
- componentes base
- design system

Saídas esperadas:
- componentes reutilizáveis
- base visual consistente

## Etapa 4 — Público
Objetivos:
- home
- estoque
- detalhe do veículo
- contato
- financiamento
- vender veículo
- páginas institucionais
- blog

## Etapa 5 — Admin
Objetivos:
- login
- dashboard
- CRUD de veículos
- CRUD de leads
- CRUD de páginas/posts
- configurações

## Etapa 6 — Integrações
Objetivos:
- storage
- e-mail
- captcha
- analytics
- sentry

## Etapa 7 — QA e deploy
Objetivos:
- corrigir type errors
- melhorar responsividade
- configurar deploy
- publicar demo

## Modo de trabalho exigido ao Cursor
- sempre ler `docs/` antes de implementar
- propor plano antes de alterar arquivos
- executar em lotes pequenos
- manter aderência aos documentos
- atualizar README quando necessário
- não inventar escopo fora da documentação sem marcar como sugestão
