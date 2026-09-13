-- Phase 10 Frente A: conversation ownership (botStatus + ownershipRevision).
-- Apply order: after 20260908120000_sdr_commercial_crm_sync.
-- Do not apply this migration to remote Supabase in this phase.
-- HANDOFF_SENT remains "vendor notified, AI still active".
-- HUMAN_ACTIVE is explicit assume. AI_RESUMED is authorized resume.
-- Lead.status is not changed by assume/resume.

ALTER TYPE "facilcar"."ConversationBotStatus" ADD VALUE IF NOT EXISTS 'AI_RESUMED';

ALTER TABLE "facilcar"."Conversation"
  ADD COLUMN IF NOT EXISTS "ownershipRevision" INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS "assumedByUserId" TEXT,
  ADD COLUMN IF NOT EXISTS "assumedAt" TIMESTAMP(3),
  ADD COLUMN IF NOT EXISTS "resumedByUserId" TEXT,
  ADD COLUMN IF NOT EXISTS "resumedAt" TIMESTAMP(3),
  ADD COLUMN IF NOT EXISTS "resumeReason" TEXT;

CREATE INDEX IF NOT EXISTS "Conversation_assumedByUserId_idx"
  ON "facilcar"."Conversation"("assumedByUserId");
