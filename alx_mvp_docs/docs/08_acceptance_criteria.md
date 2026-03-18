# Acceptance Criteria

## Produto pronto para demo quando:

### Público
- home carrega sem erros
- estoque lista veículos publicados
- filtros funcionam
- detalhe do veículo carrega corretamente
- CTA de WhatsApp funciona
- formulários enviam dados persistidos
- páginas institucionais carregam
- blog simples funciona

### Admin
- login admin funciona
- é possível criar veículo
- é possível editar veículo
- é possível publicar/despublicar veículo
- é possível enviar e ordenar imagens
- é possível listar e atualizar leads
- é possível editar páginas institucionais
- é possível editar posts

### Infra
- ambiente público acessível
- banco persistindo dados
- storage funcionando
- e-mail/notificação funcionando ou claramente mockado
- analytics básico ativo
- monitoramento básico ativo

### Qualidade
- responsivo em mobile e desktop
- sem erros críticos no console
- sem rotas quebradas
- sem dados hardcoded sensíveis
- build de produção estável

## Critérios por funcionalidade
### Estoque
- filtro por marca funciona
- filtro por combustível funciona
- busca textual funciona
- paginação funciona

### Veículo
- ao menos 3 imagens mockadas no seed para alguns veículos
- ficha técnica clara
- preço exibido de forma consistente

### Lead
- lead salvo com tipo e origem
- lead de veículo salva `vehicleId`
- lead aparece no admin

### Conteúdo
- páginas e posts respeitam status de publicação
