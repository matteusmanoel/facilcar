# CURRENT_DOMAIN_MAP — Existing Prisma / DB Models

> Source: `apps/web/prisma/schema.prisma` + applied migrations (production)
> PostgreSQL schema: `facilcar`
> Last migration: `20260812120000_catalog_import_staging`

## Confirmed Existing Models

### User
```
id, name, email (unique), passwordHash, role (UserRole), isActive, lastLoginAt, createdAt, updatedAt
assignedLeads → Lead[]
```
**Roles**: SUPER_ADMIN, ADMIN, EDITOR, LEAD_MANAGER
**RBAC in web app**:
- LEAD_MANAGER: can read/write leads and customers
- ADMIN / SUPER_ADMIN: full access
- EDITOR: content only

**Current prod users**: Milton Barrios (ADMIN) + admin@facilcar.demo (SUPER_ADMIN). No LEAD_MANAGER users.

---

### Customer
```
id, name, phone (unique), email?, createdAt, updatedAt
leads → Lead[]
```
**Invariant**: unique by phone (digits only). Name is mutable.
**Prod count**: 0 rows (schema live, no customers yet)

---

### Lead
```
id, type (LeadType), status (LeadStatus), source (LeadSource), channel (LeadChannel)
name, email?, phone, whatsapp?, city?, state?, message?
vehicleId? → Vehicle, customerId? → Customer
assignedToUserId? → User
utm[Source|Medium|Campaign|Term|Content]?, originUrl?
metadataJson? (Json), internalNote?
deletedAt? (soft delete), createdAt, updatedAt
financingRequest? → FinancingRequest
sellRequest? → SellRequest
```

**LeadType** (confirmed in schema + julia_integration migration):
CONTACT, VEHICLE_INTEREST, FINANCING, SELL_VEHICLE, REFINANCING, TRADE_IN, CONSIGNMENT, THIRD_PARTY_FINANCING

**LeadStatus**: NEW, IN_PROGRESS, CONTACTED, QUALIFIED, WON, LOST, SPAM
> Note: SDR docs say NEW→QUALIFIED→WON/LOST. IN_PROGRESS, CONTACTED, SPAM are human-managed states. SDR uses NEW and transitions to QUALIFIED. No conflict.

**LeadSource** (includes Julia migration addition):
HOME, CATALOG, VEHICLE_PAGE, CONTACT_PAGE, FINANCING_PAGE, SELL_PAGE, BLOG, **WHATSAPP**, UNKNOWN

**LeadChannel**: FORM, WHATSAPP, MANUAL

**WON side-effect**: if `vehicleId` set and vehicle is PUBLISHED/RESERVED → marks vehicle SOLD (implemented in `updateLeadStatusAction`).

**Prod count**: 0 rows

---

### FinancingRequest (1:1 with Lead)
```
id, leadId (unique), vehicleId?
cpf?, birthDate?, hasDriverLicense?, downPayment?, desiredInstallments?
monthlyIncome?, vehicleYear?, vehicleModel?, occupation?, notes?
```
Slots available for SDR pre-ficha. No CPF/renda is mandatory for handoff.

---

### SellRequest (1:1 with Lead)
```
id, leadId (unique)
brand?, model?, version?, yearManufacture?, yearModel?, mileage?
fuelType (string)?, transmission (string)?, observations?
```
Used for SELL_VEHICLE and CONSIGNMENT leads. Also maps to trade-in vehicle data.

---

### Vehicle
```
id, slug (unique), status (VehicleStatus), type (VehicleType), title, ...
brandId → Brand, model, version?, year[Manufacture|Model]?
mileage?, fuelType?, transmission?, color?, doors?, plateFinal?
priceCash?, priceTradeIn?, pricePromotional?
city?, state?
featured, aceitaTroca, aceitaSemEntrada    ← Julia fields
parcelaBase?, entradaMinima?, rendaMinimaSugerida?, prioridade   ← Julia fields
publishedAt?, createdAt, updatedAt
images → VehicleImage[], features → VehicleFeature[]
leads → Lead[], financingRequests → FinancingRequest[]
```

**Stock rule**: Only `status=PUBLISHED` is commercially available (enforced in `listPublicVehicles`).

**Julia fields status**: Added in migration `20260504000000_julia_integration`. ALL zero/false in production — not yet filled by the store. Do not use as policy until populated.

**Production inventory**: 40 PUBLISHED + 1 DRAFT. All CAR type. All have `priceCash`. Range R$8,900–136,900, median R$52,900.

**Data gaps**: 24/41 missing mileage, 38/41 missing color, 10/41 missing transmission, 2/41 missing year.

---

### VehicleImage
```
id, vehicleId, url, alt?, sortOrder, isCover, createdAt
```

---

### SiteSettings
```
id, siteName, defaultWhatsappNumber, defaultEmail, phoneNumber?
addressLine?, city?, state?, zipCode?
facebookUrl?, instagramUrl?, youtubeUrl?
seoDefault[Title|Description]?, footerText?, heroTitle?, heroSubtitle?
publicTheme
```
**Current values**: city=Cascavel/PR, address=R. Ipanema 1206, WA=5545999974232, email=miltonvendas@hotmail.com

---

### CatalogImport* Tables (existing, used for catalog import — NOT SDR)
CatalogImportEvent, CatalogImportItem, CatalogMediaAsset, CatalogMediaBlob
These process vendor WhatsApp messages into Vehicle drafts. Separate from customer SDR flow.

---

## Tables NOT YET EXISTING (Required for SDR)

| Entity | Purpose | Priority |
|--------|---------|---------|
| **Conversation / Thread** | WhatsApp thread state (bot/human, language, summary, last_message_at, handoff state) | Wave 0 — CRITICAL |
| **Message** | Per-message storage (provider_message_id, direction, content_type, media ref, from_me) | Wave 0 — CRITICAL |
| **VisitInterest** | Simple interest record linked to Lead (date/period optional, no calendar) | Wave 2 |
| **SdrDocument** | Links uploaded sensitive doc to Lead (type: CNH/CRLV/income/residence, storage key, extracted JSON) | Wave 3 |
| **SdrNotification** | New qualified lead notification queue for web panel | Wave 4 |

---

## State Machine Alignment

| Prisma `LeadStatus` | SDR State | Usage |
|---------------------|-----------|-------|
| NEW | Initial state, bot active | SDR creates leads as NEW |
| IN_PROGRESS | Human-managed | Not used by SDR |
| CONTACTED | Human-managed | Not used by SDR |
| QUALIFIED | SDR handoff completed | SDR transitions here on handoff |
| WON | Human-managed | Seller closes deal |
| LOST | Human-managed | Seller marks lost |
| SPAM | Human-managed | Seller marks spam |

Conversation `status` (Thread model, new):
BOT_ACTIVE → QUALIFYING → READY_FOR_HANDOFF → HANDOFF_SENT → HUMAN_ACTIVE → HUMAN_CLOSED

---

## Customer Resolution Rule (existing, from `features/customer/server/upsert.ts`)
- Customer is unique by phone (digits only)
- Admin UI prompts for name reconciliation when name diverges
- SDR must follow same phone-normalization convention
- `Lead.customerId` should always be set when Customer is resolved
