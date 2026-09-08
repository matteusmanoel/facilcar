/**
 * SDR-owned quoted/reply extraction from Evolution message payloads.
 *
 * Catalog-import's parser only inspects extendedTextMessage / top-level
 * contextInfo. Customer replies on image/document/video bubbles carry
 * contextInfo on those nested objects — extract them here without editing
 * the catalog-import owner.
 */

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : null;
}

const CONTEXT_HOSTS = [
  "extendedTextMessage",
  "imageMessage",
  "documentMessage",
  "videoMessage",
  "audioMessage",
] as const;

export type SdrQuotedContext = {
  stanzaId: string;
  quotedType: string | null;
  quotedText: string | null;
};

function quotedPayloadFromMessage(
  quotedMessage: Record<string, unknown> | null,
): { type: string | null; text: string | null } {
  if (!quotedMessage) return { type: null, text: null };
  if (typeof quotedMessage.conversation === "string" && quotedMessage.conversation.trim()) {
    return {
      type: "conversation",
      text: quotedMessage.conversation.trim().slice(0, 500),
    };
  }
  for (const key of [
    "extendedTextMessage",
    "imageMessage",
    "videoMessage",
    "documentMessage",
  ] as const) {
    const block = asRecord(quotedMessage[key]);
    if (!block) continue;
    const caption = block.caption ?? block.text;
    const text =
      typeof caption === "string" && caption.trim()
        ? caption.trim().slice(0, 500)
        : null;
    return { type: key, text };
  }
  return { type: null, text: null };
}

export function extractSdrQuotedContext(
  message: Record<string, unknown> | null,
): SdrQuotedContext | null {
  if (!message) return null;
  const infos: Record<string, unknown>[] = [];
  for (const host of CONTEXT_HOSTS) {
    const block = asRecord(message[host]);
    const ctx = asRecord(block?.contextInfo);
    if (ctx) infos.push(ctx);
  }
  const top = asRecord(message.contextInfo);
  if (top) infos.push(top);

  for (const ctx of infos) {
    const sid = ctx.stanzaId ?? ctx.quotedStanzaId;
    if (typeof sid !== "string" || !sid.trim()) continue;
    const extracted = quotedPayloadFromMessage(asRecord(ctx.quotedMessage));
    return {
      stanzaId: sid.trim(),
      quotedType: extracted.type,
      quotedText: extracted.text,
    };
  }
  return null;
}
