# Routes and Pages

## Rotas públicas

### /
Home comercial.
Seções recomendadas:
- hero principal
- busca rápida de veículos
- destaques/featured vehicles
- benefícios/diferenciais
- bloco de financiamento
- bloco de venda de veículo
- depoimentos
- CTA para WhatsApp

### /estoque
Listagem de veículos com:
- grid de cards
- filtros
- ordenação
- paginação
- empty state

### /estoque/[slug]
Detalhe do veículo com:
- galeria
- resumo principal
- preço
- ficha técnica
- opcionais
- descrição
- CTA WhatsApp
- formulário de interesse
- veículos relacionados

### /contato
- formulário geral
- dados de contato
- WhatsApp
- endereço/mapa opcional

### /financiamento
- formulário dedicado
- campos mínimos financeiros
- contextualização do serviço

### /vender-seu-veiculo
- formulário com dados do veículo
- vantagens do processo

### /quem-somos
- conteúdo institucional

### /blog
- lista de posts

### /blog/[slug]
- detalhe do post

### /politica-de-privacidade
### /termos-de-uso
Páginas legais.

## Rotas administrativas

### /admin/login
Login administrativo.

### /admin
Dashboard inicial.
Widgets mínimos:
- veículos publicados
- leads novos
- leads do mês
- últimos leads

### /admin/veiculos
Listagem admin de veículos.
Recursos:
- buscar
- filtrar por status
- criar
- editar
- duplicar opcional
- arquivar

### /admin/veiculos/novo
Cadastro de veículo.

### /admin/veiculos/[id]
Edição de veículo.

### /admin/leads
Listagem de leads.
Filtros:
- status
- tipo
- origem
- período

### /admin/leads/[id]
Visualização/edição de lead.

### /admin/paginas
Listagem de páginas institucionais.

### /admin/paginas/[id]
Edição de página.

### /admin/blog
Listagem de posts.

### /admin/blog/[id]
Edição de post.

### /admin/configuracoes
Configurações gerais.

## Componentes de página reaproveitáveis
- header público
- footer público
- hero section
- vehicle card
- filter bar
- section heading
- CTA block
- lead form card
- empty state
- pagination
- admin data table
- status badge
- image uploader
