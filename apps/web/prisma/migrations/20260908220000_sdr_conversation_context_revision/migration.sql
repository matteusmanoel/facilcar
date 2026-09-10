-- Additive. Conversation.contextRevision is the inbound CAS token captured
-- onto FollowUpTask at create time. Default 0 means "no inbound yet";
-- follow-up create/send must refuse revision < 1 (fail-safe, no send).
ALTER TABLE "facilcar"."Conversation"
ADD COLUMN IF NOT EXISTS "contextRevision" INTEGER NOT NULL DEFAULT 0;
