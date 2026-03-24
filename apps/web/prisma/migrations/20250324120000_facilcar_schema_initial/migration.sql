-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "facilcar";

-- CreateEnum
CREATE TYPE "facilcar"."UserRole" AS ENUM ('SUPER_ADMIN', 'ADMIN', 'EDITOR', 'LEAD_MANAGER');

-- CreateEnum
CREATE TYPE "facilcar"."VehicleStatus" AS ENUM ('DRAFT', 'PUBLISHED', 'RESERVED', 'SOLD', 'ARCHIVED');

-- CreateEnum
CREATE TYPE "facilcar"."VehicleType" AS ENUM ('CAR', 'MOTORCYCLE', 'UTILITY', 'OTHER');

-- CreateEnum
CREATE TYPE "facilcar"."FuelType" AS ENUM ('GASOLINE', 'ETHANOL', 'FLEX', 'DIESEL', 'ELECTRIC', 'HYBRID', 'OTHER');

-- CreateEnum
CREATE TYPE "facilcar"."Transmission" AS ENUM ('MANUAL', 'AUTOMATIC', 'AUTOMATED', 'CVT', 'OTHER');

-- CreateEnum
CREATE TYPE "facilcar"."LeadType" AS ENUM ('CONTACT', 'VEHICLE_INTEREST', 'FINANCING', 'SELL_VEHICLE');

-- CreateEnum
CREATE TYPE "facilcar"."LeadStatus" AS ENUM ('NEW', 'IN_PROGRESS', 'CONTACTED', 'QUALIFIED', 'WON', 'LOST', 'SPAM');

-- CreateEnum
CREATE TYPE "facilcar"."LeadSource" AS ENUM ('HOME', 'CATALOG', 'VEHICLE_PAGE', 'CONTACT_PAGE', 'FINANCING_PAGE', 'SELL_PAGE', 'BLOG', 'UNKNOWN');

-- CreateEnum
CREATE TYPE "facilcar"."LeadChannel" AS ENUM ('FORM', 'WHATSAPP', 'MANUAL');

-- CreateEnum
CREATE TYPE "facilcar"."PageStatus" AS ENUM ('DRAFT', 'PUBLISHED');

-- CreateEnum
CREATE TYPE "facilcar"."PostStatus" AS ENUM ('DRAFT', 'PUBLISHED');

-- CreateEnum
CREATE TYPE "facilcar"."VehicleFeatureCategory" AS ENUM ('COMFORT', 'SAFETY', 'TECH', 'EXTERIOR', 'OTHER');

-- CreateTable
CREATE TABLE "facilcar"."User" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "role" "facilcar"."UserRole" NOT NULL,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "lastLoginAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."Brand" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "logoUrl" TEXT,
    "isActive" BOOLEAN NOT NULL DEFAULT true,

    CONSTRAINT "Brand_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."Vehicle" (
    "id" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "status" "facilcar"."VehicleStatus" NOT NULL,
    "type" "facilcar"."VehicleType" NOT NULL,
    "title" TEXT NOT NULL,
    "shortDescription" TEXT,
    "description" TEXT,
    "brandId" TEXT NOT NULL,
    "model" TEXT NOT NULL,
    "version" TEXT,
    "yearManufacture" INTEGER,
    "yearModel" INTEGER,
    "mileage" INTEGER,
    "fuelType" "facilcar"."FuelType",
    "transmission" "facilcar"."Transmission",
    "color" TEXT,
    "doors" INTEGER,
    "plateFinal" TEXT,
    "priceCash" DECIMAL(12,2),
    "priceTradeIn" DECIMAL(12,2),
    "pricePromotional" DECIMAL(12,2),
    "city" TEXT,
    "state" TEXT,
    "featured" BOOLEAN NOT NULL DEFAULT false,
    "publishedAt" TIMESTAMP(3),
    "metaTitle" TEXT,
    "metaDescription" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Vehicle_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."VehicleImage" (
    "id" TEXT NOT NULL,
    "vehicleId" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "alt" TEXT,
    "sortOrder" INTEGER NOT NULL,
    "isCover" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "VehicleImage_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."VehicleFeature" (
    "id" TEXT NOT NULL,
    "vehicleId" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "category" "facilcar"."VehicleFeatureCategory" NOT NULL,
    "sortOrder" INTEGER NOT NULL,

    CONSTRAINT "VehicleFeature_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."Lead" (
    "id" TEXT NOT NULL,
    "type" "facilcar"."LeadType" NOT NULL,
    "status" "facilcar"."LeadStatus" NOT NULL DEFAULT 'NEW',
    "source" "facilcar"."LeadSource" NOT NULL,
    "channel" "facilcar"."LeadChannel" NOT NULL,
    "name" TEXT NOT NULL,
    "email" TEXT,
    "phone" TEXT NOT NULL,
    "whatsapp" TEXT,
    "city" TEXT,
    "state" TEXT,
    "message" TEXT,
    "vehicleId" TEXT,
    "assignedToUserId" TEXT,
    "utmSource" TEXT,
    "utmMedium" TEXT,
    "utmCampaign" TEXT,
    "utmTerm" TEXT,
    "utmContent" TEXT,
    "originUrl" TEXT,
    "metadataJson" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Lead_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."FinancingRequest" (
    "id" TEXT NOT NULL,
    "leadId" TEXT NOT NULL,
    "vehicleId" TEXT,
    "hasDriverLicense" BOOLEAN,
    "downPayment" DECIMAL(12,2),
    "desiredInstallments" INTEGER,
    "monthlyIncome" DECIMAL(12,2),
    "occupation" TEXT,
    "notes" TEXT,

    CONSTRAINT "FinancingRequest_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."SellRequest" (
    "id" TEXT NOT NULL,
    "leadId" TEXT NOT NULL,
    "brand" TEXT,
    "model" TEXT,
    "version" TEXT,
    "yearManufacture" INTEGER,
    "yearModel" INTEGER,
    "mileage" INTEGER,
    "fuelType" TEXT,
    "transmission" TEXT,
    "observations" TEXT,

    CONSTRAINT "SellRequest_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."Page" (
    "id" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "excerpt" TEXT,
    "body" TEXT NOT NULL,
    "status" "facilcar"."PageStatus" NOT NULL,
    "metaTitle" TEXT,
    "metaDescription" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Page_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."BlogPost" (
    "id" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "excerpt" TEXT,
    "coverImageUrl" TEXT,
    "body" TEXT NOT NULL,
    "status" "facilcar"."PostStatus" NOT NULL,
    "publishedAt" TIMESTAMP(3),
    "metaTitle" TEXT,
    "metaDescription" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "BlogPost_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."SiteSettings" (
    "id" TEXT NOT NULL,
    "siteName" TEXT NOT NULL,
    "defaultWhatsappNumber" TEXT NOT NULL,
    "defaultEmail" TEXT NOT NULL,
    "phoneNumber" TEXT,
    "addressLine" TEXT,
    "city" TEXT,
    "state" TEXT,
    "zipCode" TEXT,
    "facebookUrl" TEXT,
    "instagramUrl" TEXT,
    "youtubeUrl" TEXT,
    "seoDefaultTitle" TEXT,
    "seoDefaultDescription" TEXT,
    "footerText" TEXT,
    "heroTitle" TEXT,
    "heroSubtitle" TEXT,

    CONSTRAINT "SiteSettings_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "facilcar"."User"("email");

-- CreateIndex
CREATE UNIQUE INDEX "Brand_name_key" ON "facilcar"."Brand"("name");

-- CreateIndex
CREATE UNIQUE INDEX "Brand_slug_key" ON "facilcar"."Brand"("slug");

-- CreateIndex
CREATE UNIQUE INDEX "Vehicle_slug_key" ON "facilcar"."Vehicle"("slug");

-- CreateIndex
CREATE INDEX "Vehicle_status_idx" ON "facilcar"."Vehicle"("status");

-- CreateIndex
CREATE INDEX "Vehicle_featured_idx" ON "facilcar"."Vehicle"("featured");

-- CreateIndex
CREATE INDEX "Vehicle_brandId_idx" ON "facilcar"."Vehicle"("brandId");

-- CreateIndex
CREATE INDEX "Vehicle_priceCash_idx" ON "facilcar"."Vehicle"("priceCash");

-- CreateIndex
CREATE INDEX "Vehicle_fuelType_idx" ON "facilcar"."Vehicle"("fuelType");

-- CreateIndex
CREATE INDEX "Vehicle_transmission_idx" ON "facilcar"."Vehicle"("transmission");

-- CreateIndex
CREATE INDEX "Vehicle_publishedAt_idx" ON "facilcar"."Vehicle"("publishedAt");

-- CreateIndex
CREATE INDEX "Lead_type_idx" ON "facilcar"."Lead"("type");

-- CreateIndex
CREATE INDEX "Lead_status_idx" ON "facilcar"."Lead"("status");

-- CreateIndex
CREATE INDEX "Lead_source_idx" ON "facilcar"."Lead"("source");

-- CreateIndex
CREATE INDEX "Lead_createdAt_idx" ON "facilcar"."Lead"("createdAt" DESC);

-- CreateIndex
CREATE UNIQUE INDEX "FinancingRequest_leadId_key" ON "facilcar"."FinancingRequest"("leadId");

-- CreateIndex
CREATE UNIQUE INDEX "SellRequest_leadId_key" ON "facilcar"."SellRequest"("leadId");

-- CreateIndex
CREATE UNIQUE INDEX "Page_slug_key" ON "facilcar"."Page"("slug");

-- CreateIndex
CREATE UNIQUE INDEX "BlogPost_slug_key" ON "facilcar"."BlogPost"("slug");

-- AddForeignKey
ALTER TABLE "facilcar"."Vehicle" ADD CONSTRAINT "Vehicle_brandId_fkey" FOREIGN KEY ("brandId") REFERENCES "facilcar"."Brand"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "facilcar"."VehicleImage" ADD CONSTRAINT "VehicleImage_vehicleId_fkey" FOREIGN KEY ("vehicleId") REFERENCES "facilcar"."Vehicle"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "facilcar"."VehicleFeature" ADD CONSTRAINT "VehicleFeature_vehicleId_fkey" FOREIGN KEY ("vehicleId") REFERENCES "facilcar"."Vehicle"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "facilcar"."Lead" ADD CONSTRAINT "Lead_vehicleId_fkey" FOREIGN KEY ("vehicleId") REFERENCES "facilcar"."Vehicle"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "facilcar"."Lead" ADD CONSTRAINT "Lead_assignedToUserId_fkey" FOREIGN KEY ("assignedToUserId") REFERENCES "facilcar"."User"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "facilcar"."FinancingRequest" ADD CONSTRAINT "FinancingRequest_leadId_fkey" FOREIGN KEY ("leadId") REFERENCES "facilcar"."Lead"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "facilcar"."FinancingRequest" ADD CONSTRAINT "FinancingRequest_vehicleId_fkey" FOREIGN KEY ("vehicleId") REFERENCES "facilcar"."Vehicle"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "facilcar"."SellRequest" ADD CONSTRAINT "SellRequest_leadId_fkey" FOREIGN KEY ("leadId") REFERENCES "facilcar"."Lead"("id") ON DELETE CASCADE ON UPDATE CASCADE;
