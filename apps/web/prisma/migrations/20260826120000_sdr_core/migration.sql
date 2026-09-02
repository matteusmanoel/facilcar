-- Júlia SDR core (WP-000): Conversation, Message, VisitInterest, SdrDocument, SdrNotification + Lead columns

-- CreateEnum
CREATE TYPE "facilcar"."ConversationBotStatus" AS ENUM (
  'BOT_ACTIVE',
  'QUALIFYING',
  'READY_FOR_HANDOFF',
  'HANDOFF_SENT',
  'HUMAN_ACTIVE',
  'HUMAN_CLOSED'
);

-- CreateEnum
CREATE TYPE "facilcar"."MessageDirection" AS ENUM ('INBOUND', 'OUTBOUND');

-- CreateEnum
CREATE TYPE "facilcar"."MessageContentType" AS ENUM (
  'TEXT',
  'AUDIO',
  'IMAGE',
  'DOCUMENT',
  'VIDEO',
  'STICKER',
  'UNKNOWN'
);

-- CreateEnum
CREATE TYPE "facilcar"."SdrDocumentType" AS ENUM (
  'CNH',
  'CRLV',
  'INCOME_PROOF',
  'RESIDENCE_PROOF',
  'OTHER'
);

-- CreateEnum
CREATE TYPE "facilcar"."SdrDocumentExtractionStatus" AS ENUM ('PENDING', 'DONE', 'FAILED');

-- CreateEnum
CREATE TYPE "facilcar"."SdrRetentionPolicy" AS ENUM ('PERMANENT', 'DAYS_180');

-- CreateEnum
CREATE TYPE "facilcar"."SdrNotificationType" AS ENUM ('NEW_QUALIFIED', 'NEW_HOT_LEAD');

-- CreateEnum
CREATE TYPE "facilcar"."LeadTemperature" AS ENUM ('HOT', 'WARM', 'COLD');

-- CreateTable
CREATE TABLE "facilcar"."Conversation" (
    "id" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "instanceName" TEXT NOT NULL,
    "botStatus" "facilcar"."ConversationBotStatus" NOT NULL DEFAULT 'BOT_ACTIVE',
    "language" TEXT,
    "accumulatedSummary" TEXT,
    "lastMessageAt" TIMESTAMP(3),
    "activeLeadIds" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "handoffAt" TIMESTAMP(3),
    "canonicalStateJson" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Conversation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."Message" (
    "id" TEXT NOT NULL,
    "conversationId" TEXT NOT NULL,
    "providerMessageId" TEXT NOT NULL,
    "instanceName" TEXT NOT NULL,
    "direction" "facilcar"."MessageDirection" NOT NULL,
    "contentType" "facilcar"."MessageContentType" NOT NULL,
    "text" TEXT,
    "mediaStorageKey" TEXT,
    "mediaMimeType" TEXT,
    "transcription" TEXT,
    "fromMe" BOOLEAN NOT NULL,
    "isHumanSent" BOOLEAN NOT NULL DEFAULT false,
    "isBotSent" BOOLEAN NOT NULL DEFAULT false,
    "language" TEXT,
    "turnFactsJson" JSONB,
    "processingStatus" TEXT DEFAULT 'PENDING',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "processedAt" TIMESTAMP(3),

    CONSTRAINT "Message_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."VisitInterest" (
    "id" TEXT NOT NULL,
    "leadId" TEXT NOT NULL,
    "conversationId" TEXT,
    "dateHint" TEXT,
    "period" TEXT,
    "notes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "VisitInterest_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."SdrDocument" (
    "id" TEXT NOT NULL,
    "leadId" TEXT,
    "conversationId" TEXT,
    "documentType" "facilcar"."SdrDocumentType" NOT NULL,
    "storageKey" TEXT NOT NULL,
    "mimeType" TEXT,
    "byteSize" INTEGER,
    "extractedJson" JSONB,
    "extractionStatus" "facilcar"."SdrDocumentExtractionStatus" NOT NULL DEFAULT 'PENDING',
    "retentionPolicy" "facilcar"."SdrRetentionPolicy" NOT NULL DEFAULT 'DAYS_180',
    "expiresAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SdrDocument_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "facilcar"."SdrNotification" (
    "id" TEXT NOT NULL,
    "leadId" TEXT NOT NULL,
    "type" "facilcar"."SdrNotificationType" NOT NULL,
    "seenAt" TIMESTAMP(3),
    "seenByUserId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SdrNotification_pkey" PRIMARY KEY ("id")
);

-- AlterTable Lead (additive columns)
ALTER TABLE "facilcar"."Lead"
  ADD COLUMN IF NOT EXISTS "juliaSummary" TEXT,
  ADD COLUMN IF NOT EXISTS "temperature" "facilcar"."LeadTemperature",
  ADD COLUMN IF NOT EXISTS "conversationId" TEXT;

-- CreateIndex Conversation
CREATE UNIQUE INDEX "Conversation_instanceName_phone_key" ON "facilcar"."Conversation"("instanceName", "phone");
CREATE INDEX "Conversation_phone_idx" ON "facilcar"."Conversation"("phone");

-- CreateIndex Message
CREATE UNIQUE INDEX "Message_instanceName_providerMessageId_key" ON "facilcar"."Message"("instanceName", "providerMessageId");
CREATE INDEX "Message_conversationId_createdAt_idx" ON "facilcar"."Message"("conversationId", "createdAt");

-- CreateIndex VisitInterest
CREATE INDEX "VisitInterest_leadId_idx" ON "facilcar"."VisitInterest"("leadId");
CREATE INDEX "VisitInterest_conversationId_idx" ON "facilcar"."VisitInterest"("conversationId");

-- CreateIndex SdrDocument
CREATE INDEX "SdrDocument_leadId_idx" ON "facilcar"."SdrDocument"("leadId");
CREATE INDEX "SdrDocument_conversationId_idx" ON "facilcar"."SdrDocument"("conversationId");

-- CreateIndex SdrNotification
CREATE INDEX "SdrNotification_seenAt_createdAt_idx" ON "facilcar"."SdrNotification"("seenAt", "createdAt");
CREATE INDEX "SdrNotification_leadId_idx" ON "facilcar"."SdrNotification"("leadId");

-- CreateIndex Lead
CREATE INDEX IF NOT EXISTS "Lead_conversationId_idx" ON "facilcar"."Lead"("conversationId");

-- AddForeignKey Message
ALTER TABLE "facilcar"."Message"
  ADD CONSTRAINT "Message_conversationId_fkey"
  FOREIGN KEY ("conversationId") REFERENCES "facilcar"."Conversation"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey VisitInterest
ALTER TABLE "facilcar"."VisitInterest"
  ADD CONSTRAINT "VisitInterest_leadId_fkey"
  FOREIGN KEY ("leadId") REFERENCES "facilcar"."Lead"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "facilcar"."VisitInterest"
  ADD CONSTRAINT "VisitInterest_conversationId_fkey"
  FOREIGN KEY ("conversationId") REFERENCES "facilcar"."Conversation"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey SdrDocument
ALTER TABLE "facilcar"."SdrDocument"
  ADD CONSTRAINT "SdrDocument_leadId_fkey"
  FOREIGN KEY ("leadId") REFERENCES "facilcar"."Lead"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "facilcar"."SdrDocument"
  ADD CONSTRAINT "SdrDocument_conversationId_fkey"
  FOREIGN KEY ("conversationId") REFERENCES "facilcar"."Conversation"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey SdrNotification
ALTER TABLE "facilcar"."SdrNotification"
  ADD CONSTRAINT "SdrNotification_leadId_fkey"
  FOREIGN KEY ("leadId") REFERENCES "facilcar"."Lead"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey Lead → Conversation
ALTER TABLE "facilcar"."Lead"
  ADD CONSTRAINT "Lead_conversationId_fkey"
  FOREIGN KEY ("conversationId") REFERENCES "facilcar"."Conversation"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;
