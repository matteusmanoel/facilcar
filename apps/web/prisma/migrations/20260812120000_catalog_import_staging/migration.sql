-- CreateEnum
CREATE TYPE "facilcar"."CatalogEventStatus" AS ENUM ('RECEIVED', 'QUEUED', 'PROCESSING', 'PROCESSED', 'IGNORED', 'FAILED');

-- CreateEnum
CREATE TYPE "facilcar"."CatalogItemStatus" AS ENUM ('COLLECTING', 'READY', 'PROCESSING', 'IMPORTED', 'FAILED');

-- CreateEnum
CREATE TYPE "facilcar"."CatalogMediaStatus" AS ENUM ('PENDING', 'UPLOADED', 'FAILED', 'SKIPPED_DEDUPED');

-- CreateEnum
CREATE TYPE "facilcar"."CatalogTextKind" AS ENUM ('VEHICLE_START', 'CONTINUATION', 'MEDIA_ONLY', 'UNKNOWN');

-- CreateTable
CREATE TABLE "facilcar"."CatalogImportItem" (
    "id" TEXT NOT NULL,
    "sessionKey" TEXT NOT NULL,
    "sourceMessageId" TEXT,
    "rawText" TEXT,
    "parsedJson" JSONB,
    "vehicleFingerprint" TEXT,
    "status" "facilcar"."CatalogItemStatus" NOT NULL DEFAULT 'COLLECTING',
    "vehicleId" TEXT,
    "lockedAt" TIMESTAMP(3),
    "lockedBy" TEXT,
    "attemptCount" INTEGER NOT NULL DEFAULT 0,
    "lastAttemptAt" TIMESTAMP(3),
    "idleClosedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "error" TEXT,
    "warnings" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CatalogImportItem_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."CatalogImportEvent" (
    "id" TEXT NOT NULL,
    "instance" TEXT NOT NULL,
    "messageId" TEXT NOT NULL,
    "remoteJid" TEXT,
    "fromMe" BOOLEAN NOT NULL,
    "messageType" TEXT,
    "textKind" "facilcar"."CatalogTextKind",
    "waTimestamp" TIMESTAMP(3),
    "sequence" INTEGER NOT NULL,
    "payloadHash" TEXT NOT NULL,
    "rawPayload" JSONB NOT NULL,
    "rawPayloadTruncated" BOOLEAN NOT NULL DEFAULT false,
    "text" TEXT,
    "hasMedia" BOOLEAN NOT NULL DEFAULT false,
    "mediaRef" JSONB,
    "mediaStatus" "facilcar"."CatalogMediaStatus",
    "processingStatus" "facilcar"."CatalogEventStatus" NOT NULL DEFAULT 'RECEIVED',
    "importItemId" TEXT,
    "error" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CatalogImportEvent_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."CatalogMediaBlob" (
    "id" TEXT NOT NULL,
    "sha256" TEXT NOT NULL,
    "storageKey" TEXT NOT NULL,
    "publicUrl" TEXT NOT NULL,
    "mimeType" TEXT,
    "byteSize" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CatalogMediaBlob_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."CatalogMediaAsset" (
    "id" TEXT NOT NULL,
    "importItemId" TEXT NOT NULL,
    "eventId" TEXT,
    "blobId" TEXT,
    "sortOrder" INTEGER NOT NULL DEFAULT 0,
    "status" "facilcar"."CatalogMediaStatus" NOT NULL DEFAULT 'PENDING',
    "error" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CatalogMediaAsset_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "CatalogImportItem_sessionKey_status_idx" ON "facilcar"."CatalogImportItem"("sessionKey", "status");

-- CreateIndex
CREATE INDEX "CatalogImportItem_status_lockedAt_idx" ON "facilcar"."CatalogImportItem"("status", "lockedAt");

-- CreateIndex
CREATE INDEX "CatalogImportItem_vehicleFingerprint_idx" ON "facilcar"."CatalogImportItem"("vehicleFingerprint");

-- CreateIndex
CREATE UNIQUE INDEX "CatalogImportEvent_instance_messageId_key" ON "facilcar"."CatalogImportEvent"("instance", "messageId");

-- CreateIndex
CREATE INDEX "CatalogImportEvent_processingStatus_createdAt_idx" ON "facilcar"."CatalogImportEvent"("processingStatus", "createdAt");

-- CreateIndex
CREATE INDEX "CatalogImportEvent_importItemId_sequence_idx" ON "facilcar"."CatalogImportEvent"("importItemId", "sequence");

-- CreateIndex
CREATE UNIQUE INDEX "CatalogMediaBlob_sha256_key" ON "facilcar"."CatalogMediaBlob"("sha256");

-- CreateIndex
CREATE UNIQUE INDEX "CatalogMediaAsset_eventId_key" ON "facilcar"."CatalogMediaAsset"("eventId");

-- CreateIndex
CREATE INDEX "CatalogMediaAsset_importItemId_sortOrder_idx" ON "facilcar"."CatalogMediaAsset"("importItemId", "sortOrder");

-- AddForeignKey
ALTER TABLE "facilcar"."CatalogImportEvent" ADD CONSTRAINT "CatalogImportEvent_importItemId_fkey" FOREIGN KEY ("importItemId") REFERENCES "facilcar"."CatalogImportItem"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "facilcar"."CatalogMediaAsset" ADD CONSTRAINT "CatalogMediaAsset_importItemId_fkey" FOREIGN KEY ("importItemId") REFERENCES "facilcar"."CatalogImportItem"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "facilcar"."CatalogMediaAsset" ADD CONSTRAINT "CatalogMediaAsset_blobId_fkey" FOREIGN KEY ("blobId") REFERENCES "facilcar"."CatalogMediaBlob"("id") ON DELETE SET NULL ON UPDATE CASCADE;
