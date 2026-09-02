-- Additive CRM: customer notes, N:N lead vehicle interest, customer documents.

ALTER TABLE "facilcar"."Customer" ADD COLUMN "notes" TEXT;

CREATE TABLE "facilcar"."LeadVehicleInterest" (
    "id" TEXT NOT NULL,
    "leadId" TEXT NOT NULL,
    "vehicleId" TEXT NOT NULL,
    "isPrimary" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "LeadVehicleInterest_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "LeadVehicleInterest_leadId_vehicleId_key"
  ON "facilcar"."LeadVehicleInterest"("leadId", "vehicleId");

CREATE INDEX "LeadVehicleInterest_leadId_idx"
  ON "facilcar"."LeadVehicleInterest"("leadId");

CREATE INDEX "LeadVehicleInterest_vehicleId_idx"
  ON "facilcar"."LeadVehicleInterest"("vehicleId");

ALTER TABLE "facilcar"."LeadVehicleInterest"
  ADD CONSTRAINT "LeadVehicleInterest_leadId_fkey"
  FOREIGN KEY ("leadId") REFERENCES "facilcar"."Lead"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "facilcar"."LeadVehicleInterest"
  ADD CONSTRAINT "LeadVehicleInterest_vehicleId_fkey"
  FOREIGN KEY ("vehicleId") REFERENCES "facilcar"."Vehicle"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

CREATE TABLE "facilcar"."CustomerDocument" (
    "id" TEXT NOT NULL,
    "customerId" TEXT NOT NULL,
    "fileName" TEXT NOT NULL,
    "storageKey" TEXT NOT NULL,
    "mimeType" TEXT,
    "byteSize" INTEGER,
    "documentType" TEXT NOT NULL DEFAULT 'CONTRACT',
    "retentionPolicy" "facilcar"."SdrRetentionPolicy" NOT NULL DEFAULT 'PERMANENT',
    "uploadedByUserId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CustomerDocument_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "CustomerDocument_customerId_idx"
  ON "facilcar"."CustomerDocument"("customerId");

ALTER TABLE "facilcar"."CustomerDocument"
  ADD CONSTRAINT "CustomerDocument_customerId_fkey"
  FOREIGN KEY ("customerId") REFERENCES "facilcar"."Customer"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;
