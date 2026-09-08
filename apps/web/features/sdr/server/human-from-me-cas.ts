import type { ConversationBotStatus } from "@prisma/client";

const SKIP_HUMAN_FROM_ME: ConversationBotStatus[] = ["HUMAN_ACTIVE", "HUMAN_CLOSED"];

/** CAS patch for seller-typed fromMe. Bot echoes are excluded by ingest dedupe (isBotSent pre-insert). */
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
