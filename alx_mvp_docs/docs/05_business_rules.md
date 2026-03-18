# Business Rules

## Publicação de veículos
1. veículo pode estar em rascunho, publicado, reservado, vendido ou arquivado
2. somente veículos publicados aparecem no site público
3. veículo vendido pode continuar público apenas se política comercial permitir; no MVP, recomendação é ocultar ou sinalizar claramente
4. cada veículo deve ter pelo menos uma imagem para publicação
5. slug deve ser único

## Exibição de preços
1. `priceCash` é o preço principal exibido
2. `priceTradeIn` é opcional e só aparece se preenchido
3. `pricePromotional` substitui visualmente o preço principal quando política de exibição permitir
4. quando não houver preço, exibir CTA “consultar valor”

## Destaque de veículos
1. veículo com `featured = true` pode aparecer na home
2. home deve limitar quantidade de destaques para preservar performance

## Formulários
1. todo formulário público exige nome e telefone
2. e-mail pode ser opcional no contato rápido, mas recomendado
3. captcha obrigatório
4. ao enviar formulário, registrar origem da página
5. ao enviar lead de veículo, vincular `vehicleId`

## Leads
1. todo lead nasce com status `NEW`
2. leads podem ser atribuídos manualmente
3. mudança de status não deve apagar dados originais
4. registrar timestamps de criação e atualização

## Financiamento
1. formulário deve aceitar veículo vinculado ou consulta genérica
2. campos financeiros avançados não são obrigatórios no MVP
3. resultado do formulário não precisa gerar cálculo automático no MVP

## Venda de veículo
1. aceitar dados básicos do veículo do cliente
2. dados mais completos ficam para fase futura
3. anexos podem ficar fora do MVP para reduzir complexidade

## Conteúdo
1. páginas institucionais e posts só aparecem se `PUBLISHED`
2. slug único para páginas e posts

## Administração
1. apenas usuários autenticados podem acessar `/admin`
2. editor não pode gerenciar usuários se esse módulo não existir
3. todas as ações críticas devem ter feedback claro

## Analytics
1. rastrear visualização de home, estoque, detalhe de veículo e envio de formulário
2. rastrear cliques em WhatsApp

## SEO
1. páginas públicas devem possuir metadados mínimos
2. veículos publicados devem ter title/description derivados caso não sejam preenchidos manualmente
