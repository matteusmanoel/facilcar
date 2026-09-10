/**
 * Outbound provenance for Evolution fromMe events.
 *
 * Administrative Assumir is the only source of HUMAN_CONFIRMED ownership.
 * Evolution echoes are correlated to bot reservations when possible.
 * Anything else is AMBIGUOUS_FROM_ME and must not change ownership.
 *
 * Residual (Fase 14): Evolution cannot advertise the real id before send
 * returns. That window is fail-safe: ambiguous, no assume.
 */

export const RESERVED_BOT_PROVIDER_PREFIX = "bot-pending-";

export type FromMeAuthorship =
  | "BOT_CONFIRMED"
  | "HUMAN_CONFIRMED"
  | "AMBIGUOUS_FROM_ME"
  | "NOT_FROM_ME";

export type FromMeClassification =
  | { kind: "ignore"; reason: "not_from_me"; authorship: "NOT_FROM_ME" }
  | {
      kind: "bot_echo";
      reason: "is_bot_sent" | "known_provider_id" | "pending_reservation";
      authorship: "BOT_CONFIRMED";
    }
  | {
      kind: "human";
      reason: "admin_assume";
      authorship: "HUMAN_CONFIRMED";
    }
  | {
      kind: "ambiguous";
      reason:
        | "missing_provider_id"
        | "unmatched_from_me"
        | "divergent_text"
        | "early_echo";
      authorship: "AMBIGUOUS_FROM_ME";
    };

export function normalizeProviderMessageId(
  id: string | null | undefined,
): string {
  return (id ?? "").trim();
}

export function isReservedBotProviderId(
  id: string | null | undefined,
): boolean {
  return normalizeProviderMessageId(id).startsWith(
    RESERVED_BOT_PROVIDER_PREFIX,
  );
}

export function pendingBotReservationWhere(input: {
  conversationId: string;
  instanceName: string;
  text?: string | null;
}): {
  conversationId: string;
  instanceName: string;
  isBotSent: true;
  providerMessageId: { startsWith: string };
  text: string;
} | null {
  const text = (input.text ?? "").trim();
  if (!text) return null;
  return {
    conversationId: input.conversationId,
    instanceName: input.instanceName,
    isBotSent: true,
    providerMessageId: { startsWith: RESERVED_BOT_PROVIDER_PREFIX },
    text,
  };
}

export function classifyFromMeProvenance(input: {
  fromMe: boolean;
  providerMessageId?: string | null;
  existingIsBotSent?: boolean | null;
  knownBotProviderId?: boolean | null;
  pendingBotReservation?: boolean | null;
  textMatchesReservation?: boolean | null;
  adminAssume?: boolean | null;
}): FromMeClassification {
  if (!input.fromMe) {
    return { kind: "ignore", reason: "not_from_me", authorship: "NOT_FROM_ME" };
  }
  if (input.adminAssume) {
    return { kind: "human", reason: "admin_assume", authorship: "HUMAN_CONFIRMED" };
  }
  if (input.existingIsBotSent) {
    return { kind: "bot_echo", reason: "is_bot_sent", authorship: "BOT_CONFIRMED" };
  }
  if (input.knownBotProviderId) {
    return {
      kind: "bot_echo",
      reason: "known_provider_id",
      authorship: "BOT_CONFIRMED",
    };
  }
  if (input.pendingBotReservation) {
    if (input.textMatchesReservation === false) {
      return {
        kind: "ambiguous",
        reason: "divergent_text",
        authorship: "AMBIGUOUS_FROM_ME",
      };
    }
    return {
      kind: "bot_echo",
      reason: "pending_reservation",
      authorship: "BOT_CONFIRMED",
    };
  }
  if (!normalizeProviderMessageId(input.providerMessageId)) {
    return {
      kind: "ambiguous",
      reason: "missing_provider_id",
      authorship: "AMBIGUOUS_FROM_ME",
    };
  }
  if (isReservedBotProviderId(input.providerMessageId)) {
    return {
      kind: "ambiguous",
      reason: "early_echo",
      authorship: "AMBIGUOUS_FROM_ME",
    };
  }
  return {
    kind: "ambiguous",
    reason: "unmatched_from_me",
    authorship: "AMBIGUOUS_FROM_ME",
  };
}

export function shouldAssumeHumanFromMe(
  classification: FromMeClassification,
): boolean {
  return classification.authorship === "HUMAN_CONFIRMED";
}
