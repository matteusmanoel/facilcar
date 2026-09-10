-- Phase 11: durable SDR opt-out on Conversation.
-- Survives /deletar (reset_conversation_memory must not NULL this column).
-- Does not replace botStatus, ownershipRevision, or FollowUpTask.status.
-- Do not apply this migration to remote Supabase in this phase.

ALTER TABLE "facilcar"."Conversation"
  ADD COLUMN IF NOT EXISTS "sdrOptedOutAt" TIMESTAMP(3);
