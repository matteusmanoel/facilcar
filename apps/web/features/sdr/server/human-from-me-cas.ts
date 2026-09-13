import type { ConversationBotStatus } from "@prisma/client";

const SKIP_HUMAN_FROM_ME: ConversationBotStatus[] = ["HUMAN_ACTIVE", "HUMAN_CLOSED"];

/**
 * CAS patch reserved for HUMAN_CONFIRMED ownership only.
 *
 * Ingest webhooks must not call this for unmatched fromMe, real Evolution ids,
 * or missing bot rows. Administrative Assumir in conversation-ownership.ts is
 * the current HUMAN_CONFIRMED source. Device fromMe cannot set assumedByUserId.
 */
export function humanFromMeOwnershipCas(input: {
  conversationId: string;
  ownershipRevision: number;
  botStatus: ConversationBotStatus;
  handoffAt: Date | null;
  lastAt: Date;
}) {
  if (SKIP_HUMAN_FROM_ME.includes(input.botStatus)) return null;
  return {
    where: {
      id: input.conversationId,
      ownershipRevision: input.ownershipRevision,
      botStatus: { notIn: SKIP_HUMAN_FROM_ME },
    },
    data: {
      botStatus: "HUMAN_ACTIVE" as const,
      handoffAt: input.handoffAt ?? input.lastAt,
      ownershipRevision: { increment: 1 },
    },
  };
}
