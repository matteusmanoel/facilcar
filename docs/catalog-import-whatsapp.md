# Catalog import via WhatsApp (Evolution local)

Importa anúncios do **remetente allowlistado** recebidos na instância Evolution (número receptor) para `Vehicle` em status **DRAFT**. Sem Meta Cloud API, Vision, filas externas ou publicação automática.

## Arquitetura

```
Evolution :8081 → POST /api/webhooks/evolution → CatalogImportEvent
  → worker (claim) → classificador → Item → parse/OpenAI texto
  → mídia (sha256 → CatalogMediaBlob) → Storage → TX Prisma → DRAFT
```

## Pré-requisitos

1. App Next com `DATABASE_URL` + storage (`STORAGE_*`) + `OPENAI_API_KEY` (opcional no inspect).
2. Migration `20260812120000_catalog_import_staging` aplicada (`npm run db:deploy`).
3. Evolution local na porta **8081**.

## Evolution local

```bash
cp .env.evolution.example .env.evolution
# edite AUTHENTICATION_API_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD

npm run evolution:up
npm run evolution:logs
```

Crie a instância (ex. `facilcar`) na UI/API Evolution. **Não fique regenerando QR em loop** se o app retornar *"Can't link new devices"* — isso agrava rate-limit.

Webhook (Evolution → Next local):

- URL: `http://host.docker.internal:3000/api/webhooks/evolution` (Colima/Docker Desktop)
- Header: `Authorization: Bearer <CATALOG_IMPORT_SECRET>` ou `x-catalog-import-secret`
- Eventos: mensagens (`MESSAGES_UPSERT` / equivalente v2)

### Fingerprint do companion

No compose / `.env.evolution`:

```bash
CONFIG_SESSION_PHONE_CLIENT=Chrome
CONFIG_SESSION_PHONE_NAME=Chrome
```

Evite nomes customizados (ex. `FacilCar`) no `CLIENT` — o Baileys anuncia isso no handshake.

### Passkey / “Can't link new devices” (Shortcake)

Se `web.whatsapp.com` conecta normalmente mas o QR do Evolution falha imediatamente (ou o app diz *try again later*), a conta provavelmente exige **passkey (WebAuthn)** no vínculo de companion. Evolution **v2.3.7 + Baileys** não completa esse passo → QR inútil.

**Cooldownção operacional (sem upgrade cego):**

1. **Cooldown:** pare de gerar QR por algumas horas; deixe a instance em `close` (não em `connecting`).
2. No Chrome, faça login em `https://web.whatsapp.com` e complete o passo de passkey no celular.
3. Extraia a sessão companion do browser (extensão/extractor baseado no fluxo community, ex. [whatsapp-session-extractor](https://github.com/marcoscarraro/whatsapp-session-extractor) — referenciado em [Evolution #2618](https://github.com/evolution-foundation/evolution-api/issues/2618)).
4. Salve o JSON exportado (gitignored) e importe na instance local:

```bash
node scripts/evolution-import-wa-creds.mjs /caminho/export-sessao.json
# confirma com y → grava Session.creds e chama /instance/connect/facilcar
```

5. **Feche a aba do WhatsApp Web** que doou a sessão (mesmo companion; dois clientes na mesma credencial conflitam).
6. Confirme `GET /instance/connectionState/facilcar` → `open`.

Não commitar o JSON de creds. Não reabrir QR em massa enquanto o rate-limit estiver ativo.

Referência: Meta “Shortcake” / passkey companion linking; workaround = assumir o companion do browser em vez de parear device novo.

## Variáveis (apps/web/.env)

Para a campanha (Next + worker + Prisma no **mesmo** alvo prod):

| Camada | Arquivos | Notas |
|---|---|---|
| Next.js | `.env` → `.env.local` | **não** carrega `.env.prod` |
| CLI inspect/worker/retry | `.env` → `.env.local` (override) → `.env.prod` (só preenche faltantes) | |
| Prisma CLI | `.env` → `.env.local` (shell `DATABASE_URL` vence) | migrate: preferir URL direta se alcançável |
| Evolution compose | root `.env.evolution` | isolado; porta 8081 |

Na prática da Fase 0, use `apps/web/.env.local` com `DATABASE_URL` + `STORAGE_*` + `CATALOG_IMPORT_*` + `EVOLUTION_*` apontando para o mesmo projeto Supabase (`oulknepjqhyiyjbiuqtg`). Mantenha `.env` local só como fallback; **não** sobrescreva `.env.prod`.

| Var | Notas |
|---|---|
| `CATALOG_IMPORT_SECRET` | Bearer do webhook |
| `CATALOG_IMPORT_ALLOWED_JIDS` | CSV dos **remetentes** do catálogo (peer). O receptor é o número da instance Evolution — não precisa estar nesta lista. Inclua variantes com/sem o 9 do celular se o WA normalizar diferente. |
| `CATALOG_IMPORT_IDLE_MS` | default `45000` — fecha `COLLECTING→READY` |
| `CATALOG_IMPORT_LOCK_TIMEOUT_MS` | default `300000` |
| `CATALOG_IMPORT_MODE` | `inspect` (Fase 0) ou `import` |
| `EVOLUTION_API_URL` | `http://localhost:8081` |
| `EVOLUTION_API_KEY` | = `AUTHENTICATION_API_KEY` |
| `EVOLUTION_INSTANCE` | ex. `facilcar` |

## Fluxo operacional

1. Do chip do catálogo (allowlist), **enviar** o anúncio para o número da instance Evolution (receptor). `fromMe` no Evolution fica `false`; o peer allowlistado é o remetente (`remoteJid` / `remoteJidAlt`).
2. Webhook grava evento (dedupe `(instance, messageId)`).
3. Worker agrupa e processa:

```bash
# Fase 0 — não cria Vehicle, não faz upload Storage, não cria VehicleImage
CATALOG_IMPORT_MODE=inspect npm run catalog-import:inspect

# Produção local da campanha
CATALOG_IMPORT_MODE=import npm run catalog-import:worker

# Retry de um item
npm run catalog-import:retry -- <itemId>
```

Em `inspect`, o worker faz parse (determinístico/OpenAI texto) e **pula** mídia + `createDraft`.

4. Revisar DRAFTs no admin; publicar manualmente.

## Classificação (determinística)

| Kind | Quando |
|---|---|
| `VEHICLE_START` | headline com marca / produto estruturado |
| `CONTINUATION` | preço, km, câmbio, texto curto anexável |
| `MEDIA_ONLY` | mídia sem texto significativo |
| `UNKNOWN` | ignorado |

OpenAI **nunca** decide agrupamento — só extrai campos de texto após o Item fechar.

## Fase 0 — casos A–D (inspect)

Antes de `CATALOG_IMPORT_MODE=import`, encaminhe e rode `catalog-import:inspect`. Confirme staging + classificação.

### Caso A — anúncio completo em uma mensagem

Texto tipo: `Honda Civic 2020\nR$ 98.900\n32.000 km\nAutomático` (+ foto opcional).

Esperado: 1 `CatalogImportEvent` `VEHICLE_START`, 1 Item após idle/próximo start, parse com brand/model/price.

### Caso B — continuação textual

1. `Honda HR-V 2019`
2. `R$ 112.000`
3. `45.000 km`
4. `Único dono` + foto

Esperado: **1 Item**, rawText concatenado, assets ordenados por `sequence`.

### Caso C — dois veículos

1. `Civic EXL 2021` + foto  
2. `Corolla XEi 2020` + foto  

Esperado: **2 Items** (segundo `VEHICLE_START` fecha o primeiro como `READY`).

### Caso D — mídia órfã / remetente fora da allowlist

Esperado: evento `IGNORED` ou webhook 200 sem persistir; nada vira Vehicle.

Salve payloads sanitizados (sem base64) como fixtures em `apps/web/features/catalog-import/fixtures/` após validar A–D.

## Retry seguro

- `IMPORTED` → no-op  
- Reusa `parsedJson` e blobs por `sha256`  
- Nunca cria segundo Vehicle se `vehicleId` já setado  
- Storage OK + TX falhou → retry só refaz TX  

## Scripts

| Script | Onde |
|---|---|
| `npm run evolution:up\|down\|logs` | root |
| `npm run catalog-import:worker\|inspect\|retry` | root → apps/web |
| `npm run test:unit` | root → vitest |

## Fora de escopo

Meta Commerce, Vision, n8n, Evolution em produção, painel de importações, publicação automática.
