/**
 * Outbound provenance for Evolution fromMe events.
 *
 * Not every fromMe=true is a human seller. Júlia's own bubbles are echoed
 * back with fromMe=true; those rows are correlated by isBotSent and/or a
 * known providerMessageId. Device/human outbound is fromMe without that
 * correlation — but only when a provider id was present to look up.
 *
 * Residual TOCTOU: the worker still send_text then insert_bot_outbound.
 * An echo that arrives before the bot row exists, carrying a real Evolution
 * id, can still look unmatched. Ingest must not invent ownership when the
 * provider id is missing; it cannot close the remaining send-then-insert race
 * without reserving the id before send.
 */

export type FromMeClassification =
  | { kind: "ignore"; reason: "not_from_me" }
  | { kind: "insufficient"; reason: "missing_provider_id" }
  | { kind: "bot_echo"; reason: "is_bot_sent" | "known_provider_id" }
  | { kind: "human"; reason: "unmatched_from_me" };

export function normalizeProviderMessageId(
  id: string | null | undefined,
): string {
  return (id ?? "").trim();
}

export function classifyFromMeProvenance(input: {
  fromMe: boolean;
  providerMessageId?: string | null;
  existingIsBotSent?: boolean | null;
  knownBotProviderId?: boolean | null;
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
  return { kind: "human", reason: "unmatched_from_me" };
}

export function shouldAssumeHumanFromMe(
  classification: FromMeClassification,
): boolean {
  return classification.kind === "human";
}
