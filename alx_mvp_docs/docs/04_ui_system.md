# UI System

## Diretriz geral
Visual premium, limpo, objetivo e com foco em conversão. O produto deve parecer confiável, rápido e comercialmente forte.

## Princípios
- foco em fotos de veículos
- hierarquia tipográfica clara
- CTAs visíveis
- poucos elementos por seção
- espaçamento generoso
- excelente experiência mobile
- consistência visual entre público e admin

## Tom visual
- moderno
- automotivo premium
- sem excesso de ornamento
- alto contraste para legibilidade

## Stack de UI
- Tailwind CSS
- shadcn/ui
- Lucide
- class-variance-authority
- tailwind-merge
- Framer Motion apenas em microinterações relevantes

## Tokens sugeridos
### Cores
- background: neutro claro ou escuro controlado
- foreground: neutro alto contraste
- primary: cor institucional definida pelo cliente
- secondary: cinza/escuro de apoio
- accent: cor para destaque moderado
- destructive: vermelho padrão
- success: verde para feedback
- warning: âmbar para alerta

### Tipografia
- heading: fonte sans forte e contemporânea
- body: sans de alta legibilidade
- pesos: 400, 500, 600, 700

### Radius
- cards: 16px a 24px
- inputs: 12px a 16px
- botões: 14px a 18px

### Shadow
- baixa a média, sem exagero

## Componentes principais
### VehicleCard
Deve conter:
- imagem capa
- badge de destaque/status opcional
- título
- preço
- atributos rápidos
- CTA ver detalhes

### FilterBar
- busca
- selects principais
- faixa de preço opcional
- botão limpar filtros

### VehicleHero
- imagem principal
- galeria lateral ou carrossel
- preço
- dados-chave
- CTAs principais

### LeadForm
- curto e claro
- labels explícitas
- feedback de envio
- captcha

### AdminTable
- paginação
- filtros
- ação por linha
- badge de status

## Padrões de interação
- CTA principal sempre visível acima da dobra em páginas de conversão
- formulário nunca excessivamente longo no MVP
- estados de loading e erro explícitos
- skeletons em listagens
- confirmação clara em ações do admin

## Responsividade
### Mobile
- prioridade máxima
- galeria com swipe
- filtros em drawer
- CTA sticky opcional em detalhe de veículo

### Desktop
- grid arejado
- sidebar de filtros se fizer sentido
- área admin com densidade moderada

## SEO/UI
- headings semânticos
- metadados configuráveis
- imagens otimizadas
- páginas rápidas
