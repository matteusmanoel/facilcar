-- Additive operational inventory: stock type, commercial history, full plate,
-- internal pricing, partners/ownership, and import audit. No destructive changes.

CREATE TYPE "facilcar"."VehicleStockType" AS ENUM ('OWNED', 'CONSIGNED');

CREATE TYPE "facilcar"."VehicleCommercialHistory" AS ENUM ('CLEAN', 'AUCTION', 'RECOVERED_CLAIM', 'AUCTION_AND_RECOVERED_CLAIM');

ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "plate" TEXT;
ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "priceFipe" DECIMAL(12,2);
ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "priceRetailWithWarranty" DECIMAL(12,2);
ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "priceRetailAsIs" DECIMAL(12,2);
ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "priceOwnerAsking" DECIMAL(12,2);
ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "stockType" "facilcar"."VehicleStockType";
ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "commercialHistory" "facilcar"."VehicleCommercialHistory";
ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "commercialHistoryRaw" TEXT;
ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "sourceRawDescription" TEXT;
ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "spreadsheetKey" TEXT;
ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "lastSpreadsheetSeenAt" TIMESTAMP(3);

CREATE UNIQUE INDEX "Vehicle_plate_key" ON "facilcar"."Vehicle"("plate");
CREATE UNIQUE INDEX "Vehicle_spreadsheetKey_key" ON "facilcar"."Vehicle"("spreadsheetKey");
CREATE INDEX "Vehicle_stockType_idx" ON "facilcar"."Vehicle"("stockType");
CREATE INDEX "Vehicle_commercialHistory_idx" ON "facilcar"."Vehicle"("commercialHistory");

CREATE TABLE "facilcar"."Partner" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Partner_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "Partner_name_key" ON "facilcar"."Partner"("name");
CREATE UNIQUE INDEX "Partner_slug_key" ON "facilcar"."Partner"("slug");

CREATE TABLE "facilcar"."VehicleOwner" (
    "vehicleId" TEXT NOT NULL,
    "partnerId" TEXT NOT NULL,
    "sharePercent" DECIMAL(5,2),

    CONSTRAINT "VehicleOwner_pkey" PRIMARY KEY ("vehicleId","partnerId")
);

CREATE INDEX "VehicleOwner_partnerId_idx" ON "facilcar"."VehicleOwner"("partnerId");

ALTER TABLE "facilcar"."VehicleOwner" ADD CONSTRAINT "VehicleOwner_vehicleId_fkey" FOREIGN KEY ("vehicleId") REFERENCES "facilcar"."Vehicle"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "facilcar"."VehicleOwner" ADD CONSTRAINT "VehicleOwner_partnerId_fkey" FOREIGN KEY ("partnerId") REFERENCES "facilcar"."Partner"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE TABLE "facilcar"."VehicleInventoryImportRun" (
    "id" TEXT NOT NULL,
    "sourceFile" TEXT NOT NULL,
    "schemaVersion" TEXT,
    "dryRun" BOOLEAN NOT NULL,
    "applied" BOOLEAN NOT NULL DEFAULT false,
    "summary" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "VehicleInventoryImportRun_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "VehicleInventoryImportRun_createdAt_idx" ON "facilcar"."VehicleInventoryImportRun"("createdAt");

CREATE TABLE "facilcar"."VehicleInventoryImportItem" (
    "id" TEXT NOT NULL,
    "runId" TEXT NOT NULL,
    "spreadsheetKey" TEXT NOT NULL,
    "plateNormalized" TEXT,
    "action" TEXT NOT NULL,
    "confidence" TEXT NOT NULL,
    "vehicleId" TEXT,
    "notes" TEXT,
    "payload" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "VehicleInventoryImportItem_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "VehicleInventoryImportItem_runId_idx" ON "facilcar"."VehicleInventoryImportItem"("runId");
CREATE INDEX "VehicleInventoryImportItem_vehicleId_idx" ON "facilcar"."VehicleInventoryImportItem"("vehicleId");
CREATE INDEX "VehicleInventoryImportItem_spreadsheetKey_idx" ON "facilcar"."VehicleInventoryImportItem"("spreadsheetKey");

ALTER TABLE "facilcar"."VehicleInventoryImportItem" ADD CONSTRAINT "VehicleInventoryImportItem_runId_fkey" FOREIGN KEY ("runId") REFERENCES "facilcar"."VehicleInventoryImportRun"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "facilcar"."VehicleInventoryImportItem" ADD CONSTRAINT "VehicleInventoryImportItem_vehicleId_fkey" FOREIGN KEY ("vehicleId") REFERENCES "facilcar"."Vehicle"("id") ON DELETE SET NULL ON UPDATE CASCADE;
