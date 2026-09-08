import type { ConversationBotStatus } from "@prisma/client";

const SKIP_HUMAN_FROM_ME: ConversationBotStatus[] = ["HUMAN_ACTIVE", "HUMAN_CLOSED"];

/**
 * CAS patch for seller-typed fromMe on this conversation only.
 *
 * Caller must already classify provenance (isBotSent / known providerMessageId /
 * missing id). Device fromMe cannot set assumedByUserId — the WhatsApp echo
 * has no CRM user. Authorized Assumir in conversation-ownership.ts owns that.
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
