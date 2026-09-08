-- Phase 2: private document storage status, stable key, message correlation.

CREATE TYPE "facilcar"."SdrDocumentStorageStatus" AS ENUM (
  'PENDING',
  'PROCESSING',
  'STORED',
  'RETRYABLE_FAILURE',
  'PERMANENT_FAILURE'
);

ALTER TABLE "facilcar"."SdrDocument"
  ALTER COLUMN "storageKey" DROP NOT NULL;

ALTER TABLE "facilcar"."SdrDocument"
  ADD COLUMN IF NOT EXISTS "messageId" TEXT,
  ADD COLUMN IF NOT EXISTS "providerMessageId" TEXT,
  ADD COLUMN IF NOT EXISTS "storageBucket" TEXT,
  ADD COLUMN IF NOT EXISTS "storageStatus" "facilcar"."SdrDocumentStorageStatus" NOT NULL DEFAULT 'PENDING',
  ADD COLUMN IF NOT EXISTS "storageAttempts" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS "storageError" TEXT,
  ADD COLUMN IF NOT EXISTS "storageUpdatedAt" TIMESTAMP(3),
  ADD COLUMN IF NOT EXISTS "contentHash" TEXT;

UPDATE "facilcar"."SdrDocument"
SET "storageStatus" = CASE
      WHEN "storageKey" LIKE 'stub/%' THEN 'RETRYABLE_FAILURE'::"facilcar"."SdrDocumentStorageStatus"
      WHEN "storageKey" IS NOT NULL AND btrim("storageKey") <> '' THEN 'STORED'::"facilcar"."SdrDocumentStorageStatus"
      ELSE 'PENDING'::"facilcar"."SdrDocumentStorageStatus"
    END,
    "storageUpdatedAt" = COALESCE("storageUpdatedAt", "createdAt");

ALTER TABLE "facilcar"."SdrDocument"
  ADD CONSTRAINT "SdrDocument_messageId_fkey"
  FOREIGN KEY ("messageId") REFERENCES "facilcar"."Message"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

CREATE INDEX "SdrDocument_messageId_idx" ON "facilcar"."SdrDocument"("messageId");
CREATE INDEX "SdrDocument_storageStatus_idx" ON "facilcar"."SdrDocument"("storageStatus");

CREATE UNIQUE INDEX "SdrDocument_conversationId_providerMessageId_key"
  ON "facilcar"."SdrDocument"("conversationId", "providerMessageId");
