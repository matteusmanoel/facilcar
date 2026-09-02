# Regras de Cliente e Lead

## Identificação por telefone

- Cada **cliente** é único por telefone normalizado (apenas dígitos).
- Leads manuais e formulários públicos vinculam-se ao cliente existente quando o telefone coincide.

## Conflito de nome

Quando um lead manual é criado com telefone já cadastrado **e nome diferente** do cliente:

1. O sistema **não decide automaticamente** — exibe modal de reconciliação.
2. Opções:
   - **Manter nome do cadastro** — lead usa o nome já salvo no cliente.
   - **Atualizar para o novo nome** — cliente e lead passam a usar o nome informado.
   - **Cancelar** — nenhuma alteração.

## Cadastro manual de cliente

- Se o telefone já existir ao criar cliente, **abre o modal de edição** do registro existente (sem toast de erro genérico).

## Edição da ficha do lead

No detalhe do lead, contato e fichas já persistidas (`FinancingRequest` / `SellRequest`) entram em modo edição com Cancelar/Salvar.

- Telefone continua sendo a chave do cliente: mudar o número religa o lead via a mesma resolução de conflito de nome. Números já gravados com DDI 55 não são truncados na máscara de edição.
- O telefone do cliente antigo **não** é reescrito; o lead passa a apontar para o cliente do novo número.
- CPF mascarado só é alterado depois de **Alterar CPF** (não grava a máscara `***`).


- Formulários do site continuam fazendo upsert silencioso (atualizam nome/e-mail do cliente), pois não há operador para confirmar conflito.
