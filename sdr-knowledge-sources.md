# Fontes oficiais para o SDR Júlia

Investigação read-only (25/08/2026) no projeto Supabase `oulknepjqhyiyjbiuqtg`, schema `facilcar`, cruzada com Prisma, CMS, seed, RBAC e contrato 2026.

**Resposta curta para o plano:** respeitar o modelo de Lead/Customer já existente — ele já foi estendido para a Júlia. Não criar um CRM paralelo. Estoque e preço à vista em `Vehicle` são a fonte operacional. Conhecimento comercial institucional quase não existe no banco: está em copy genérica e, hipoteticamente, no n8n — que **não está neste repositório**. Quem valida regra de loja não é o desenvolvedor; o representante legal é Eraldo Lopes Ramos, o operador no admin é Milton Barrios. Conversas reais de venda **não estão neste banco**.

| Métrica | Valor |
|---|---|
| Veículos publicados | 40 (+ 1 DRAFT) |
| Leads / clientes / FinancingRequest | 0 / 0 / 0 |
| Páginas institucionais | 2 |
| Posts de blog em produção | 0 |
| Agenda / chat de venda | inexistente |

---

## 1. O CRM atual já tem um modelo de lead consolidado?

**Sim. Respeitar o modelo atual. Não criar outro CRM para “sincronizar depois”.**

`Lead` já é a entidade agregadora do admin/site. A migration `apps/web/prisma/migrations/20260504000000_julia_integration/migration.sql` já antecipou a Júlia:

- tipos `REFINANCING`, `TRADE_IN`, `CONSIGNMENT`, `THIRD_PARTY_FINANCING`
- source `WHATSAPP`
- campos no veículo: `aceitaTroca`, `aceitaSemEntrada`, `parcelaBase`, `entradaMinima`, `rendaMinimaSugerida`, `prioridade`

O admin já opera status, atribuição a vendedor, nota interna e soft-delete (`deletedAt`).

**Liberdade real:** tabelas novas **aditivas** (thread, mensagem, visita, score) e JSON em `Lead.metadataJson`.

**Não há liberdade** para um segundo cadastro de lead que ignore `Customer.phone` único e o pipeline `NEW → QUALIFIED → WON/LOST`.

O CRM está **vazio operacionalmente** (0 leads, 0 clientes). O schema está vivo; a operação ainda não passou por ele.

### Peças do modelo

| Peça | O que já existe | Uso em produção |
|---|---|---|
| `Lead` | `type`, `status`, `source`, `channel`, `phone`, `vehicleId`, `assignedToUserId`, `metadataJson`, `internalNote` | 0 linhas — schema vivo, CRM vazio |
| `Customer` | único por telefone normalizado; upsert nos forms; reconciliação de nome no admin | 0 linhas |
| `FinancingRequest` | 1:1 com Lead — CNH, renda, entrada, parcelas, CPF, nascimento | 0 linhas |
| `SellRequest` | 1:1 com Lead — dados do usado do cliente (venda/consignação) | 0 linhas |
| Tipos Júlia | `REFINANCING` / `TRADE_IN` / `CONSIGNMENT` / `THIRD_PARTY_FINANCING` + `channel WHATSAPP` | Prontos no enum; nenhum lead WhatsApp gravado |

Regras que o agente não deve quebrar (ver `apps/web/docs/customer-lead-rules.md`):

- Cliente único por telefone (`Customer.phone`, só dígitos)
- Lead nasce `NEW`
- `WON` em veículo `PUBLISHED`/`RESERVED` marca o carro `SOLD`
- Forms públicos fazem upsert silencioso de cliente; admin pede reconciliação se o nome divergir

Domínio documentado em `alx_mvp_docs/docs/02_domain_model.md` (ligeiramente desatualizado em relação aos tipos Júlia — o Prisma/schema de produção é a verdade).

---

## 2. Quais informações do banco são fonte oficial?

Só o que está abaixo deve ser tratado como verdade de sistema. Copy de seed, prompt de n8n e anúncios de WhatsApp do catálogo **não substituem** estas tabelas.

O site público só lista `Vehicle.status = PUBLISHED` (`listPublicVehicles` em `apps/web/features/catalog/server/queries.ts`). O SDR deve tratar o restante como indisponível.

| Domínio | Fonte oficial | Regra | Estado atual (25/08/2026) |
|---|---|---|---|
| Estoque | `facilcar.Vehicle` | Público = `PUBLISHED`. `DRAFT` / `RESERVED` / `SOLD` / `ARCHIVED` ficam fora do site. | 40 PUBLISHED + 1 DRAFT · só `CAR` · anos 2000–2024 |
| Preço | `Vehicle.priceCash` | Preço principal. `priceTradeIn` e `pricePromotional` só se preenchidos. | 41/41 com `priceCash` · R$ 8.900–136.900 · mediana R$ 52.900 · 0 troca/promo |
| Condições Júlia no carro | `aceitaTroca`, `aceitaSemEntrada`, `parcelaBase`, `entradaMinima`, `rendaMinimaSugerida`, `prioridade` | Campos de compatibilidade SDR; admin já edita (`VehicleForm`). | **Todos zerados** — não usar como política até a loja preencher |
| Fotos | `VehicleImage.url` + bucket Storage `vehicle-images` | Publicação exige ≥1 imagem (regra do MVP). | 44 imagens / 41 carros · 38 com 1 foto · 42 objetos no Storage |
| Clientes | `facilcar.Customer` | Identidade = telefone só dígitos. Lead sempre tenta vincular `customerId`. | Vazio |
| Vendedores | `facilcar.User` + `Lead.assignedToUserId` | `LEAD_MANAGER` = perfil vendedor no RBAC. `ADMIN`/`SUPER_ADMIN` também atribuem. | Milton Barrios (`ADMIN`) e `admin@facilcar.demo` (`SUPER_ADMIN`). Nenhum `LEAD_MANAGER`. |
| Leads / status | `Lead.status` + `LeadType` / `LeadSource` / `LeadChannel` | Nascimento `NEW`. Forms do site e admin manual já escrevem aqui. | Vazio |
| Agenda / visita | — | Não há tabela, enum ou tela de agendamento. | **Lacuna.** Blog seed menciona “agendar visita”; não há calendário. |
| Institucional / contato | `Page`, `BlogPost`, `SiteSettings` | Páginas só se `PUBLISHED`. | 2 páginas; 0 posts; Cascavel/PR, R. Ipanema 1206, WA `5545999974232` |
| Ingestão de estoque WA | `CatalogImportEvent` / `CatalogImportItem` / `CatalogMedia*` | Staging de anúncios WhatsApp → rascunho de `Vehicle`. **Não é conversa com cliente.** | 46 itens (44 IMPORTED, 2 FAILED) · 50 eventos · 1 JID de origem |

### Tabelas no schema `facilcar`

`BlogPost`, `Brand`, `CatalogImportEvent`, `CatalogImportItem`, `CatalogMediaAsset`, `CatalogMediaBlob`, `Customer`, `FinancingRequest`, `Lead`, `Page`, `SellRequest`, `SiteSettings`, `User`, `Vehicle`, `VehicleFeature`, `VehicleImage`.

Não existem tabelas de Conversation, Message, Transcript, Appointment, Visit, FAQ, Policy ou Playbook.

### Catálogo vivo (marcas)

| Marca | N veículos |
|---|---|
| Fiat | 12 |
| Chevrolet | 6 |
| Ford | 5 |
| Hyundai | 4 |
| Honda / Renault / Volkswagen | 3 cada |
| Jeep, Mitsubishi, Audi, Toyota, GM | 1 cada |

Chevrolet e GM duplicam a mesma marca. Completude da ficha: 24/41 sem km, 38/41 sem cor, 10/41 sem câmbio, 2/41 sem ano. O SDR **não deve inventar ficha**.

### WhatsApp persistido hoje — não é CRM

`CatalogImportEvent` guarda anúncios (`productMessage` / `imageMessage`) enviados por um remetente allowlisted para popular estoque. 48 eventos `fromMe=false`, 1 JID. Textos são legendas de catálogo, não objeções de cliente.

Exemplo: “CHEVROLET TRACKER LTZ 2014 · Price: R$ 68.900”. Pipeline Evolution → webhook → grouper → `Vehicle` DRAFT/PUBLISHED. Fora do escopo de qualificação de lead.

---

## 3. De onde virá o conhecimento institucional/comercial da Júlia?

**Não há knowledge base comercial no Supabase.** Não existe tabela de políticas, FAQ, scripts, financeiras parceiras, regras de consignação ou playbook de troca.

O que há é CMS raso + campos de veículo vazios + (fora deste repo) o workflow n8n histórico.

| Candidato a conhecimento | O que é de fato | Pode virar regra oficial? |
|---|---|---|
| `Page` `quem-somos` / `politica-de-privacidade` | 538 e 203 caracteres. Copy genérica de seminovos, financiamento e consignação **sem números, prazos ou financeiras**. | Tom institucional mínimo. Insuficiente para SDR. |
| `BlogPost` | 0 posts em produção. Seed local tem 6 artigos didáticos (entrada zero, documentos, checklist). | **Não.** Seed é conteúdo de demo, não política da loja. |
| `docs/contrato-facilcar-2026.html` | Contrato de licença de software Mateus × Facil Car Multimarcas LTDA. Define dono dos **dados da plataforma**, não regras de venda. | Não usar como playbook comercial. |
| Campos Júlia no `Vehicle` | Schema e admin prontos; 0 preenchidos. | Sim, **depois** que a loja cadastrar. Hoje = hipótese vazia. |
| `FinancingRequest` + forms `/financiamento` | Captura CNH, renda, entrada, parcelas (máx. 84). Sem cálculo CET, sem integração com financeira. | Estrutura de dados sim; regra de crédito não. |
| Prompt / workflow n8n da Júlia | Nenhum JSON n8n da Júlia neste repositório nem em `~/Projects`. Só n8n de outro produto (`appointments` / barbearia). | Tratar como **comportamento histórico** até validação humana. Não promover a política. |

Corpo atual das páginas em produção:

**quem-somos** — A FácilCar Multimarcas é uma revenda focada em seminovos com curadoria real; financiamento junto às principais financeiras; consignação; valores de honestidade, respeito ao tempo do cliente e pós-venda; visita em Cascavel/PR ou WhatsApp. Sem regras operacionais.

**politica-de-privacidade** — coleta dados de contato para atendimento comercial; não vende dados a terceiros; contato `miltonvendas@hotmail.com`.

### Implicação para o plano

O conhecimento institucional precisa ser extraído e versionado **fora do prompt**: documento curto validado pela loja (financiamento, troca, consignação, horário, o que a Júlia não pode prometer) + `Vehicle` como verdade de estoque/preço. Sem isso, o SDR vai alucinar a partir de copy de marketing.

`alx_mvp_docs/docs/05_business_rules.md` cobre publicação de veículo, exibição de preço e captura de lead do **site** — não políticas comerciais da loja (entrada mínima real, financeiras, consignação).

---

## 4. Quem valida “isso está correto para a FácilCar”?

**Não é o desenvolvedor (Mateus) e não é o JSON da Júlia.**

Mateus Ferreira é CONTRATADA (software) no contrato 2026. Não deve ser o sign-off comercial.

| Pessoa | Papel evidenciado | Pode validar regra de loja? |
|---|---|---|
| Eraldo Lopes Ramos | Representante legal da Facil Car Multimarcas LTDA (CNPJ 58.502.256/0001-87) no contrato. Endereço = `SiteSettings`. | Sim — dono de negócio / sign-off formal. Confirmar se opera o dia a dia. |
| Milton Barrios | Único ADMIN humano no banco (`miltonvendas@hotmail.com`). E-mail e WhatsApp oficiais do site. | Provável validador operacional de scripts e estoque. Confirmar com a loja. |
| Vendedor específico | Role `LEAD_MANAGER` existe; nenhum usuário com esse perfil em produção. | Não há vendedor nomeado no CRM para ser “gold standard”. |
| Mateus / agente / n8n JSON | Implementação e histórico de automação. | **Não.** Hipótese de comportamento, nunca política. |

**unconfirmed · pending validation:** quem, entre Eraldo e Milton, assina o playbook da Júlia. Isso precisa ser decidido antes de transformar comportamento histórico em política.

---

## 5. Existem conversas reais de bons vendedores?

**Não neste banco.**

Zero leads, zero customers, zero `FinancingRequest`. Não há `Conversation`, `Message`, `Transcript` nem export de WhatsApp de atendimento.

O que existe no WhatsApp persistido é ingestão de catálogo (legendas de anúncio), não diálogo comercial.

Para extrair objeções, linguagem e fluxos realistas o plano precisa de uma coleta **explícita fora do CRM atual**:

- export de conversas do número da loja (`5545999974232`)
- histórico do n8n da Júlia (se ainda existir)
- gravação supervisionada de 10–20 atendimentos bons

Sem isso, casos de teste serão sintéticos.

---

## Contexto extra para o plano do SDR

### Reutilizar

- `Lead` + `Customer` por telefone
- `channel` / `source` `WHATSAPP`
- tipos `TRADE_IN` / `CONSIGNMENT` / `FINANCING` (e os demais já no enum)
- `FinancingRequest` para slots de crédito
- `assignedToUserId` para handoff humano
- `metadataJson` para score/slots sem migration obrigatória
- `Vehicle` `PUBLISHED` como tool de estoque
- `SiteSettings` para endereço / WhatsApp / e-mail

### Criar (aditivo)

- Thread / mensagem WhatsApp (não existe)
- Visita / agenda (não existe)
- Playbook versionado validado pela loja (não existe)
- Preenchimento dos campos Júlia no veículo (schema existe, dados não)
- Usuário `LEAD_MANAGER` real
- Política de fotos (hoje ~1 por carro)

### Riscos

| Risco | Detalhe |
|---|---|
| Preço/condição incompletos | Só `priceCash` está preenchido. Sem parcela, entrada, renda mínima ou flag de troca, o agente não tem âncora de simulação. |
| Ficha técnica com buracos | Maioria sem cor e km. Responder “não consta no anúncio / confirmo na loja” em vez de completar. |
| RLS desligado em 17 tabelas | Advisory do MCP: schema `facilcar` sem RLS. O app usa Prisma server-side; ainda assim é risco se a Data API estiver aberta. Fora do escopo funcional do SDR; plano de agente com `service_role` precisa de superfície mínima. |
| Segundo projeto Supabase | `supabase/.temp` aponta `munnfnfudrsoblwgivjn` — MCP recusou permissão. Fonte usada nesta run: `oulknepjqhyiyjbiuqtg` (`apps/web/supabase/.temp`). |

### Fora de escopo desta investigação

Abrir n8n cloud, export de WhatsApp Business, ou entrevistar Eraldo/Milton.

**Bloqueantes de produto (não de schema):** playbook validado, corpus de conversas, dono de sign-off.

---

## Referências no repositório

- `apps/web/prisma/schema.prisma`
- `apps/web/prisma/migrations/20260504000000_julia_integration/migration.sql`
- `apps/web/docs/customer-lead-rules.md`
- `apps/web/features/lead/server/mutations.ts`
- `apps/web/features/lead/server/actions.ts`
- `apps/web/features/catalog/server/queries.ts`
- `apps/web/features/auth/rbac-config.ts`
- `alx_mvp_docs/docs/02_domain_model.md`
- `alx_mvp_docs/docs/05_business_rules.md`
- `docs/contrato-facilcar-2026.html`
- `docs/catalog-import-whatsapp.md`
