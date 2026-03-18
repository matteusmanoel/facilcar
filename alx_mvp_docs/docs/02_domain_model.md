# Domain Model

## Entidades centrais

## User
Representa usuários administrativos.

### Campos
- id: string UUID
- name: string
- email: string unique
- passwordHash: string
- role: enum (`SUPER_ADMIN`, `ADMIN`, `EDITOR`, `LEAD_MANAGER`)
- isActive: boolean
- lastLoginAt: datetime nullable
- createdAt: datetime
- updatedAt: datetime

## Vehicle
Representa um veículo anunciado.

### Campos
- id: string UUID
- slug: string unique
- status: enum (`DRAFT`, `PUBLISHED`, `SOLD`, `RESERVED`, `ARCHIVED`)
- type: enum (`CAR`, `MOTORCYCLE`, `UTILITY`, `OTHER`)
- title: string
- shortDescription: string nullable
- description: text nullable
- brandId: string
- model: string
- version: string nullable
- yearManufacture: int nullable
- yearModel: int nullable
- mileage: int nullable
- fuelType: enum (`GASOLINE`, `ETHANOL`, `FLEX`, `DIESEL`, `ELECTRIC`, `HYBRID`, `OTHER`)
- transmission: enum (`MANUAL`, `AUTOMATIC`, `AUTOMATED`, `CVT`, `OTHER`)
- color: string nullable
- doors: int nullable
- plateFinal: string nullable
- priceCash: decimal nullable
- priceTradeIn: decimal nullable
- pricePromotional: decimal nullable
- city: string nullable
- state: string nullable
- featured: boolean
- publishedAt: datetime nullable
- metaTitle: string nullable
- metaDescription: string nullable
- createdAt: datetime
- updatedAt: datetime

## VehicleImage
### Campos
- id: string UUID
- vehicleId: string
- url: string
- alt: string nullable
- sortOrder: int
- isCover: boolean
- createdAt: datetime

## VehicleFeature
### Campos
- id: string UUID
- vehicleId: string
- label: string
- category: enum (`COMFORT`, `SAFETY`, `TECH`, `EXTERIOR`, `OTHER`)
- sortOrder: int

## Brand
### Campos
- id: string UUID
- name: string unique
- slug: string unique
- logoUrl: string nullable
- isActive: boolean

## Lead
Entidade agregadora para qualquer entrada comercial.

### Campos
- id: string UUID
- type: enum (`CONTACT`, `VEHICLE_INTEREST`, `FINANCING`, `SELL_VEHICLE`)
- status: enum (`NEW`, `IN_PROGRESS`, `CONTACTED`, `QUALIFIED`, `WON`, `LOST`, `SPAM`)
- source: enum (`HOME`, `CATALOG`, `VEHICLE_PAGE`, `CONTACT_PAGE`, `FINANCING_PAGE`, `SELL_PAGE`, `BLOG`, `UNKNOWN`)
- channel: enum (`FORM`, `WHATSAPP`, `MANUAL`)
- name: string
- email: string nullable
- phone: string
- whatsapp: string nullable
- city: string nullable
- state: string nullable
- message: text nullable
- vehicleId: string nullable
- assignedToUserId: string nullable
- utmSource: string nullable
- utmMedium: string nullable
- utmCampaign: string nullable
- utmTerm: string nullable
- utmContent: string nullable
- originUrl: string nullable
- metadataJson: json nullable
- createdAt: datetime
- updatedAt: datetime

## FinancingRequest
Pode ser uma tabela própria ou subestrutura do Lead. Recomendado usar tabela própria ligada ao Lead.

### Campos
- id: string UUID
- leadId: string unique
- vehicleId: string nullable
- hasDriverLicense: boolean nullable
- downPayment: decimal nullable
- desiredInstallments: int nullable
- monthlyIncome: decimal nullable
- occupation: string nullable
- notes: text nullable

## SellRequest
### Campos
- id: string UUID
- leadId: string unique
- brand: string nullable
- model: string nullable
- version: string nullable
- yearManufacture: int nullable
- yearModel: int nullable
- mileage: int nullable
- fuelType: string nullable
- transmission: string nullable
- observations: text nullable

## Page
### Campos
- id: string UUID
- slug: string unique
- title: string
- excerpt: string nullable
- body: richtext/json/text
- status: enum (`DRAFT`, `PUBLISHED`)
- metaTitle: string nullable
- metaDescription: string nullable
- createdAt: datetime
- updatedAt: datetime

## BlogPost
### Campos
- id: string UUID
- slug: string unique
- title: string
- excerpt: string nullable
- coverImageUrl: string nullable
- body: richtext/json/text
- status: enum (`DRAFT`, `PUBLISHED`)
- publishedAt: datetime nullable
- metaTitle: string nullable
- metaDescription: string nullable
- createdAt: datetime
- updatedAt: datetime

## SiteSettings
### Campos
- id: string UUID
- siteName: string
- defaultWhatsappNumber: string
- defaultEmail: string
- phoneNumber: string nullable
- addressLine: string nullable
- city: string nullable
- state: string nullable
- zipCode: string nullable
- facebookUrl: string nullable
- instagramUrl: string nullable
- youtubeUrl: string nullable
- seoDefaultTitle: string nullable
- seoDefaultDescription: string nullable
- footerText: string nullable
- heroTitle: string nullable
- heroSubtitle: string nullable

## Relacionamentos
- User 1:N Lead (assigned leads)
- Brand 1:N Vehicle
- Vehicle 1:N VehicleImage
- Vehicle 1:N VehicleFeature
- Vehicle 1:N Lead
- Lead 1:0..1 FinancingRequest
- Lead 1:0..1 SellRequest

## Índices sugeridos
- Vehicle.slug unique
- Vehicle.status
- Vehicle.featured
- Vehicle.brandId
- Vehicle.priceCash
- Vehicle.fuelType
- Vehicle.transmission
- Lead.type
- Lead.status
- Lead.source
- Lead.createdAt desc
- BlogPost.slug unique
- Page.slug unique

## Observações de modelagem
- manter `Lead` como entidade central simplifica admin e relatórios
- `FinancingRequest` e `SellRequest` evitam excesso de colunas específicas em `Lead`
- `SiteSettings` evita hardcode de contato/SEO
- usar slugs normalizados para páginas públicas
