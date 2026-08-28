-- AlterTable: add Google Maps URL and coordinate fields to SiteSettings
ALTER TABLE facilcar."SiteSettings"
  ADD COLUMN IF NOT EXISTS "googleMapsUrl" TEXT,
  ADD COLUMN IF NOT EXISTS "latitude"      DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS "longitude"     DOUBLE PRECISION;
