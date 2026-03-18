# Decisões finais congeladas (MVP)

Fonte: plano em `.cursor/plans/`. Não alterar sem aprovação explícita.

## Providers
- **Banco**: Neon (PostgreSQL)
- **Storage**: Cloudflare R2 (S3-compatible)
- **Captcha**: Cloudflare Turnstile
- **Analytics**: PostHog Cloud
- **E-mail**: Resend
- **Monitoramento**: Sentry

## Formulários (campos e tipos de lead)
- **Contato**: name*, phone*, email?, message? → Lead CONTACT, source CONTACT_PAGE
- **Interesse veículo**: name*, phone*, email?, message? + vehicleId → VEHICLE_INTEREST, VEHICLE_PAGE
- **Financiamento**: name*, phone*, email?, hasDriverLicense*, monthlyIncome?, downPayment?, desiredInstallments?, notes?, vehicleId? → FINANCING, FINANCING_PAGE
- **Vender veículo**: name*, phone*, email?, observations?, brand?, model?, version?, yearManufacture?, yearModel?, mileage?, fuelType?, transmission? → SELL_VEHICLE, SELL_PAGE
- Regras: captcha obrigatório; validação Zod server-side; salvar originUrl + utm*; channel=FORM

## Filtros do catálogo
- Busca: título/marca/modelo
- Filtros: brand, type, fuelType, transmission, priceMin/priceMax, yearMin/yearMax
- Ordenação: relevance (com busca), priceAsc, priceDesc, yearDesc, mileageAsc, newest
- Paginação: page size 12

## Admin
- Auth por credenciais apenas; sem gestão de usuários no MVP; sem recuperação de senha
- Módulos: Dashboard, Veículos (CRUD + imagens), Leads (list + filtros + status), Páginas, Blog, Configurações

## Rotas públicas (slugs)
/, /estoque, /estoque/[slug], /contato, /financiamento, /vender-seu-veiculo, /quem-somos, /blog, /blog/[slug], /politica-de-privacidade, /termos-de-uso

## Seed mínimo demo
- 10 marcas, 18 veículos (4 featured), 5 páginas, 6 posts, SiteSettings completo, 1 admin (SUPER_ADMIN)
