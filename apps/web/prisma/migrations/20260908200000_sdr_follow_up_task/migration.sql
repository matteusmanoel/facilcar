-- Phase 11 Frente B: durable FollowUpTask with CAS claim.
-- Apply order: after 20260908190000_sdr_conversation_vendor_notified.
-- Do not apply this migration to remote Supabase in this phase.
-- Context is derived at send time from conversation state; do not store canonical JSON here.
-- Conversation.waitState is optional observability — it does not replace botStatus.

-- CreateEnum
CREATE TYPE "facilcar"."FollowUpTaskStatus" AS ENUM (
  'PENDING',
  'CLAIMED',
  'PROCESSING',
  'SENT',
  'CANCELLED',
  'FAILED',
  'SUPERSEDED'
);

-- AlterTable Conversation (additive waitState — does not replace botStatus)
ALTER TABLE "facilcar"."Conversation"
  ADD COLUMN IF NOT EXISTS "waitState" TEXT;

-- CreateTable
CREATE TABLE "facilcar"."FollowUpTask" (
    "id" TEXT NOT NULL,
    "conversationId" TEXT NOT NULL,
    "leadId" TEXT,
    "reason" TEXT NOT NULL,
    "status" "facilcar"."FollowUpTaskStatus" NOT NULL DEFAULT 'PENDING',
    "scheduledAt" TIMESTAMP(3) NOT NULL,
    "originalTemporalText" TEXT,
    "consentSource" TEXT,
    "consentLevel" TEXT,
    "attemptNumber" INTEGER NOT NULL DEFAULT 0,
    "maximumAttempts" INTEGER NOT NULL DEFAULT 1,
    "contextRevision" INTEGER NOT NULL DEFAULT 0,
    "ownershipRevision" INTEGER NOT NULL DEFAULT 0,
    "idempotencyKey" TEXT NOT NULL,
    "claimedAt" TIMESTAMP(3),
    "claimedBy" TEXT,
    "sentAt" TIMESTAMP(3),
    "cancelledAt" TIMESTAMP(3),
    "cancelReason" TEXT,
    "failedAt" TIMESTAMP(3),
    "lastErrorSanitized" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "FollowUpTask_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "FollowUpTask_idempotencyKey_key"
  ON "facilcar"."FollowUpTask"("idempotencyKey");

CREATE INDEX "FollowUpTask_status_scheduledAt_idx"
  ON "facilcar"."FollowUpTask"("status", "scheduledAt");

CREATE INDEX "FollowUpTask_conversationId_idx"
  ON "facilcar"."FollowUpTask"("conversationId");

ALTER TABLE "facilcar"."FollowUpTask"
  ADD CONSTRAINT "FollowUpTask_conversationId_fkey"
  FOREIGN KEY ("conversationId") REFERENCES "facilcar"."Conversation"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "facilcar"."FollowUpTask"
  ADD CONSTRAINT "FollowUpTask_leadId_fkey"
  FOREIGN KEY ("leadId") REFERENCES "facilcar"."Lead"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;
