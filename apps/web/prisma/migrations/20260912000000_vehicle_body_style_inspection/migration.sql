-- Additive: body style (car silhouette) and inspection result. Null = not informed.

CREATE TYPE "facilcar"."VehicleBodyStyle" AS ENUM ('SEDAN', 'HATCH', 'SUV');

CREATE TYPE "facilcar"."VehicleInspectionResult" AS ENUM ('APPROVED', 'REJECTED');

ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "bodyStyle" "facilcar"."VehicleBodyStyle";
ALTER TABLE "facilcar"."Vehicle" ADD COLUMN "inspectionResult" "facilcar"."VehicleInspectionResult";

CREATE INDEX "Vehicle_bodyStyle_idx" ON "facilcar"."Vehicle"("bodyStyle");
CREATE INDEX "Vehicle_inspectionResult_idx" ON "facilcar"."Vehicle"("inspectionResult");
