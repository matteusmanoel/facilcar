import type { ConversationBotStatus } from "@prisma/client";

const IA_ATENDENDO: ConversationBotStatus[] = [
  "BOT_ACTIVE",
  "QUALIFYING",
  "READY_FOR_HANDOFF",
];

/** Operational conversation indicator — not Lead.status. */
export function botStatusLabel(status: ConversationBotStatus | null | undefined): string | null {
  if (!status) return null;
  if (IA_ATENDENDO.includes(status)) return "IA atendendo";
  if (status === "HANDOFF_SENT") return "Handoff enviado, aguardando humano";
  if (status === "HUMAN_ACTIVE") return "Humano ativo";
  if (status === "AI_RESUMED") return "IA reativada";
  return null;
}

export function canAssumeConversation(
  status: ConversationBotStatus | null | undefined,
  assigned = false,
): boolean {
  if (status === "HUMAN_ACTIVE" || status === "HUMAN_CLOSED") return false;
  if (status == null) return !assigned;
  return true;
}

export function canResumeConversation(status: ConversationBotStatus | null | undefined): boolean {
  return status === "HUMAN_ACTIVE";
}
