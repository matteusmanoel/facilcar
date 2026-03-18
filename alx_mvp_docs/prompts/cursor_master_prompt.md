# Cursor Master Prompt

Leia integralmente a pasta `docs/` antes de qualquer alteração. Sua missão é construir um MVP web de revenda/estoque automotivo a partir desta documentação, respeitando rigidamente escopo, arquitetura, stack e critérios de aceite.

## Objetivo
Gerar um protótipo funcional e apresentável, cobrindo:
- home comercial
- estoque com filtros
- detalhe do veículo
- formulários de lead
- admin simples
- deploy-ready

## Regras
1. não copie assets, identidade, textos ou layout literal de benchmark externo
2. siga estritamente os documentos desta pasta
3. proponha um plano antes de editar arquivos
4. implemente em etapas pequenas e verificáveis
5. atualize README técnico quando necessário
6. preserve código limpo, tipado e modular
7. use stack definida: Next.js, TypeScript, Prisma, PostgreSQL, Tailwind, shadcn/ui, Auth.js, Zod
8. prefira server components por padrão
9. use server actions ou route handlers quando adequado
10. organize por feature

## Ordem de trabalho obrigatória
1. analisar documentação
2. criar plano de implementação
3. bootstrap do projeto
4. Prisma schema + migrations + seed
5. design system e componentes base
6. páginas públicas
7. admin
8. integrações
9. QA e correções
10. preparar deploy

## Entregas mínimas
- projeto compilando
- schema Prisma funcional
- seed com conteúdo mock
- páginas públicas essenciais
- admin protegido
- CRUD de veículos
- CRUD básico de leads
- páginas institucionais
- blog simples
- integração de storage prevista
- documentação técnica mínima

## Exigências de qualidade
- TypeScript estrito
- Zod em inputs críticos
- sem any desnecessário
- sem componentes gigantes
- sem hardcode de segredos
- responsividade real
- mensagens de erro e loading states
- build de produção passando

## Estrutura sugerida
Use a organização descrita em `docs/06_architecture.md`.

## Seed
Use `seeds/seed_content.json` como base para popular o ambiente de demonstração.

## Antes de começar a codar
Resuma:
- escopo que será implementado primeiro
- arquivos iniciais que serão criados
- riscos técnicos imediatos
- ordem dos commits lógicos
