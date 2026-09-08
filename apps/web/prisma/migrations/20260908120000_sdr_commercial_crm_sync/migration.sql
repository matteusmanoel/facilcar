-- Phase 5: commercial CRM sync — monthly payment, lead revision, visit preference.

ALTER TABLE "facilcar"."Lead"
  ADD COLUMN IF NOT EXISTS "commercialRevision" INTEGER NOT NULL DEFAULT 0;

ALTER TABLE "facilcar"."FinancingRequest"
  ADD COLUMN IF NOT EXISTS "desiredMonthlyPayment" DECIMAL(12,2);

ALTER TABLE "facilcar"."VisitInterest"
  ADD COLUMN IF NOT EXISTS "preferredDate" DATE,
  ADD COLUMN IF NOT EXISTS "preferredTime" TEXT,
  ADD COLUMN IF NOT EXISTS "originalText" TEXT,
  ADD COLUMN IF NOT EXISTS "accepted" BOOLEAN,
  ADD COLUMN IF NOT EXISTS "declined" BOOLEAN,
  ADD COLUMN IF NOT EXISTS "locationSent" BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS "interest" BOOLEAN NOT NULL DEFAULT false;
