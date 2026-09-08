-- Phase 10R Frente C: vendor notify evidence is a dispatch timestamp, not status.
-- Apply order: after 20260908180000_sdr_conversation_ownership.
-- Do not apply this migration to remote Supabase in this phase.
-- Conversation.vendorNotifiedAt is set only when HANDOFF_VENDOR persist confirms.
-- Lead.status QUALIFIED, botStatus, and handoffAt must not impersonate confirmation.

ALTER TABLE "facilcar"."Conversation"
  ADD COLUMN IF NOT EXISTS "vendorNotifiedAt" TIMESTAMP(3);
