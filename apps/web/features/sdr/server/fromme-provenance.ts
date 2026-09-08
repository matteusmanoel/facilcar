/**
 * Outbound provenance for Evolution fromMe events.
 *
 * Not every fromMe=true is a human seller. Júlia's own bubbles are echoed
 * back with fromMe=true; those rows are correlated by isBotSent and/or a
 * known providerMessageId. Device/human outbound is fromMe without that
 * correlation — but only when a provider id was present to look up.
 *
 * Worker reserves isBotSent under `bot-pending-{uuid}` before Evolution
 * send, then updates providerMessageId. An echo whose text matches an
 * open reservation is claimed (not assumed). Residual TOCTOU: Evolution
 * cannot advertise the id before send returns, so an echo with empty or
 * non-matching text still looks unmatched until that UPDATE (or claim).
 */

export const RESERVED_BOT_PROVIDER_PREFIX = "bot-pending-";

export type FromMeClassification =
  | { kind: "ignore"; reason: "not_from_me" }
  | { kind: "insufficient"; reason: "missing_provider_id" }
  | {
      kind: "bot_echo";
      reason: "is_bot_sent" | "known_provider_id" | "pending_reservation";
    }
  | { kind: "human"; reason: "unmatched_from_me" };

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
}): FromMeClassification {
  if (!input.fromMe) return { kind: "ignore", reason: "not_from_me" };
  if (!normalizeProviderMessageId(input.providerMessageId)) {
    return { kind: "insufficient", reason: "missing_provider_id" };
  }
  if (input.existingIsBotSent) {
    return { kind: "bot_echo", reason: "is_bot_sent" };
  }
  if (input.knownBotProviderId) {
    return { kind: "bot_echo", reason: "known_provider_id" };
  }
  if (input.pendingBotReservation) {
    return { kind: "bot_echo", reason: "pending_reservation" };
  }
  return { kind: "human", reason: "unmatched_from_me" };
}

export function shouldAssumeHumanFromMe(
  classification: FromMeClassification,
): boolean {
  return classification.kind === "human";
}
