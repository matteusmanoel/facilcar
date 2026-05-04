-- Julia SDR Integration: extend LeadType, LeadSource, and add Vehicle fields

-- Extend LeadType enum
ALTER TYPE "facilcar"."LeadType" ADD VALUE IF NOT EXISTS 'REFINANCING';
ALTER TYPE "facilcar"."LeadType" ADD VALUE IF NOT EXISTS 'TRADE_IN';
ALTER TYPE "facilcar"."LeadType" ADD VALUE IF NOT EXISTS 'CONSIGNMENT';
ALTER TYPE "facilcar"."LeadType" ADD VALUE IF NOT EXISTS 'THIRD_PARTY_FINANCING';

-- Extend LeadSource enum
ALTER TYPE "facilcar"."LeadSource" ADD VALUE IF NOT EXISTS 'WHATSAPP';

-- Add Julia-compatibility fields to Vehicle
ALTER TABLE "facilcar"."Vehicle"
  ADD COLUMN IF NOT EXISTS "aceitaTroca"         BOOLEAN      NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS "aceitaSemEntrada"    BOOLEAN      NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS "parcelaBase"         DECIMAL(12,2),
  ADD COLUMN IF NOT EXISTS "entradaMinima"       DECIMAL(12,2),
  ADD COLUMN IF NOT EXISTS "rendaMinimaSugerida" DECIMAL(12,2),
  ADD COLUMN IF NOT EXISTS "prioridade"          INTEGER      NOT NULL DEFAULT 0;

-- Index for vehicle ordering by priority
CREATE INDEX IF NOT EXISTS "Vehicle_prioridade_idx" ON "facilcar"."Vehicle"("prioridade");
