-- Additive: commercial engine displacement in liters (nullable).
-- No backfill. No index. Existing titles/versions are left unchanged.

ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "engineDisplacementLiters" DECIMAL(3,1);
