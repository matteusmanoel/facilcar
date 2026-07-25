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

## Leads públicos (site)

- Formulários do site continuam fazendo upsert silencioso (atualizam nome/e-mail do cliente), pois não há operador para confirmar conflito.
