# Architecture

## Visão geral
Arquitetura web monolítica modular, com frontend e backend no mesmo projeto Next.js, banco PostgreSQL e integrações externas desacopladas por serviços.

## Stack base
- Next.js (App Router)
- TypeScript
- Prisma
- PostgreSQL
- Auth.js / NextAuth
- Tailwind CSS
- shadcn/ui
- Zod
- React Hook Form

## Estratégia arquitetural
### Monólito modular
Escolha recomendada para MVP.
Vantagens:
- menor custo cognitivo
- deploy simples
- produtividade alta com IA
- menos infraestrutura
- boa base para evolução

## Organização sugerida
```txt
/apps/web
  /app
    /(public)
    /admin
    /api
  /components
  /features
    /catalog
    /vehicle
    /lead
    /content
    /settings
    /auth
    /admin
  /lib
  /schemas
  /actions
  /types
  /prisma
```

## Convenções
- organização por feature
- validação por schema Zod
- server components por padrão
- client components apenas onde necessário
- server actions para forms simples
- route handlers para casos específicos
- Prisma como camada de acesso a dados

## Camadas
### Presentation
Páginas, componentes e layouts.

### Application
Casos de uso e actions:
- createLead
- createVehicle
- updateVehicle
- publishVehicle
- listPublicVehicles
- getVehicleBySlug

### Domain
Tipos, enums e invariantes do negócio.

### Infrastructure
Prisma, storage, e-mail, analytics, captcha, monitoramento.

## Autenticação
- Auth.js com credenciais no MVP
- middleware protegendo `/admin`
- sessão via cookies seguros

## Uploads
- provider externo S3/R2/UploadThing
- salvar somente URL e metadados no banco

## E-mail
- Resend ou provider equivalente
- uso inicial: notificação interna de lead e eventual confirmação simples

## Observabilidade
- Sentry para exceções
- PostHog/GA4 para eventos
- logs básicos no servidor

## Segurança mínima
- validação server-side
- sanitização básica de inputs
- captcha
- rate limiting simples em formulários se necessário
- headers de segurança via framework/proxy

## Escalabilidade futura
A arquitetura deve facilitar:
- extração de serviços
- fila para notificações
- jobs de importação
- multi-tenant futuro
