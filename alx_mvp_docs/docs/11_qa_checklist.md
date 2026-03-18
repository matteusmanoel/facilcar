# QA Checklist

## Público
- [ ] home carrega em mobile e desktop
- [ ] estoque lista somente veículos publicados
- [ ] filtros retornam resultados corretos
- [ ] busca textual encontra marca/modelo
- [ ] empty state está ok
- [ ] detalhe exibe imagens e atributos
- [ ] CTA WhatsApp abre corretamente
- [ ] formulário de interesse salva lead
- [ ] formulário de contato salva lead
- [ ] formulário de financiamento salva lead
- [ ] formulário de venda salva lead
- [ ] páginas institucionais publicadas aparecem
- [ ] posts publicados aparecem

## Admin
- [ ] login funciona
- [ ] rotas protegidas
- [ ] criar veículo
- [ ] editar veículo
- [ ] publicar/despublicar
- [ ] upload de imagens
- [ ] ordenar imagens
- [ ] listar leads
- [ ] alterar status do lead
- [ ] editar páginas
- [ ] editar posts

## Performance / qualidade
- [ ] sem erros críticos no console
- [ ] sem erros 500 nas rotas principais
- [ ] build de produção passa
- [ ] typecheck passa
- [ ] lint passa
- [ ] imagens otimizadas

## Segurança mínima
- [ ] validação server-side
- [ ] captcha ativo
- [ ] segredos fora do código
- [ ] cookies seguros em produção
