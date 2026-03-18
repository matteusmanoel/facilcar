# Auto Dealer MVP Discovery Pack

Pacote de documentação para iniciar, no CursorIDE, o desenvolvimento de um MVP inspirado em plataformas de revenda/estoque automotivo, sem replicação literal de código, identidade visual, textos ou assets do benchmark.

## Objetivo
Entregar um protótipo funcional e comercialmente convincente para apresentação ao cliente, cobrindo:
- home comercial
- listagem de veículos
- detalhe do veículo
- formulários de lead
- admin simples
- deploy funcional

## Estrutura
- `docs/00_product_brief.md` — visão geral do produto
- `docs/01_feature_scope.md` — escopo do MVP, fora do escopo e roadmap
- `docs/02_domain_model.md` — entidades, campos e relacionamentos
- `docs/03_routes_and_pages.md` — mapa de rotas públicas e admin
- `docs/04_ui_system.md` — design system e diretrizes visuais
- `docs/05_business_rules.md` — regras de negócio
- `docs/06_architecture.md` — arquitetura da aplicação
- `docs/07_infrastructure_and_deploy.md` — infraestrutura e deploy
- `docs/08_acceptance_criteria.md` — critérios de aceite
- `docs/09_backlog.md` — backlog técnico e de produto
- `docs/10_implementation_plan.md` — plano de execução no CursorIDE
- `docs/11_qa_checklist.md` — checklist de QA
- `docs/12_risks_and_guardrails.md` — riscos, limites e salvaguardas
- `docs/13_env_matrix.md` — variáveis de ambiente e integrações
- `docs/14_demo_script.md` — roteiro de apresentação do protótipo
- `seeds/seed_content.json` — conteúdo inicial mockado
- `prompts/cursor_master_prompt.md` — prompt mestre para o CursorIDE
- `diagrams/system-overview.mmd` — diagrama Mermaid simplificado

## Premissas
- projeto web responsivo
- stack base: Next.js + TypeScript + Prisma + PostgreSQL
- deploy inicial: Vercel + Neon/Supabase + S3/R2 + Resend + Cloudflare
- foco em demonstração comercial e base escalável

## Uso recomendado no CursorIDE
1. importar este pacote no repositório
2. pedir ao Cursor para ler toda a pasta `docs/`
3. instruir o Cursor a executar o plano de `docs/10_implementation_plan.md`
4. usar `prompts/cursor_master_prompt.md` como prompt inicial de orquestração
5. exigir entrega por etapas, com commits lógicos e documentação atualizada
