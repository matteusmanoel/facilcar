-- Customer model + Lead.customerId + Lead.deletedAt (db push friendly)

CREATE TABLE "facilcar"."Customer" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "email" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Customer_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "Customer_phone_key" ON "facilcar"."Customer"("phone");
CREATE INDEX "Customer_name_idx" ON "facilcar"."Customer"("name");

ALTER TABLE "facilcar"."Lead" ADD COLUMN "customerId" TEXT;
ALTER TABLE "facilcar"."Lead" ADD COLUMN "deletedAt" TIMESTAMP(3);

CREATE INDEX "Lead_customerId_idx" ON "facilcar"."Lead"("customerId");
CREATE INDEX "Lead_deletedAt_idx" ON "facilcar"."Lead"("deletedAt");

ALTER TABLE "facilcar"."Lead" ADD CONSTRAINT "Lead_customerId_fkey" FOREIGN KEY ("customerId") REFERENCES "facilcar"."Customer"("id") ON DELETE SET NULL ON UPDATE CASCADE;
