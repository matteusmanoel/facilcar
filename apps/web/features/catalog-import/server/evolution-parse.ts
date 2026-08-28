export type NormalizedInbound = {
  instance: string;
  messageId: string;
  remoteJid: string | null;
  /** Phone alternate when `remoteJid` is a LID (`@lid`). */
  remoteJidAlt: string | null;
  fromMe: boolean;
  messageType: string | null;
  waTimestamp: Date | null;
  text: string | null;
  hasMedia: boolean;
  mediaRef: Record<string, unknown> | null;
  rawMessage: Record<string, unknown> | null;
  /** WhatsApp profile name from Evolution (`pushName` / `notifyName`). */
  pushName: string | null;
};

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function extractText(message: Record<string, unknown> | null): string | null {
  if (!message) return null;
  const conversation = message.conversation;
  if (typeof conversation === "string" && conversation.trim()) return conversation.trim();
  const ext = asRecord(message.extendedTextMessage);
  if (typeof ext?.text === "string" && ext.text.trim()) return ext.text.trim();
  const img = asRecord(message.imageMessage);
  if (typeof img?.caption === "string" && img.caption.trim()) return img.caption.trim();
  const vid = asRecord(message.videoMessage);
  if (typeof vid?.caption === "string" && vid.caption.trim()) return vid.caption.trim();
  const doc = asRecord(message.documentMessage);
  if (typeof doc?.caption === "string" && doc.caption.trim()) return doc.caption.trim();
  const product = asRecord(message.productMessage);
  const snapshot = asRecord(product?.product);
  if (typeof snapshot?.title === "string") {
    const parts = [snapshot.title, snapshot.description, snapshot.currency, snapshot.priceAmount1000]
      .filter((x) => x != null && String(x).trim())
      .map(String);
    if (parts.length) return parts.join("\n");
  }
  return null;
}

function detectMedia(message: Record<string, unknown> | null): {
  hasMedia: boolean;
  messageType: string | null;
  mediaRef: Record<string, unknown> | null;
} {
  if (!message) return { hasMedia: false, messageType: null, mediaRef: null };
  for (const key of [
    "imageMessage",
    "videoMessage",
    "documentMessage",
    "audioMessage",
    "stickerMessage",
    "productMessage",
  ]) {
    const block = asRecord(message[key]);
    if (block) {
      return {
        hasMedia: key !== "productMessage" || !!asRecord(block.product),
        messageType: key,
        mediaRef: { type: key, message: block },
      };
    }
  }
  if (typeof message.conversation === "string") {
    return { hasMedia: false, messageType: "conversation", mediaRef: null };
  }
  if (asRecord(message.extendedTextMessage)) {
    return { hasMedia: false, messageType: "extendedTextMessage", mediaRef: null };
  }
  return { hasMedia: false, messageType: null, mediaRef: null };
}

/** Evolution `pushName` / `notifyName` — never a JID or placeholder. */
export function extractWhatsAppPushName(item: Record<string, unknown>): string | null {
  const raw = item.pushName ?? item.notifyName;
  if (typeof raw !== "string") return null;
  const value = raw.trim();
  if (value.length < 2) return null;
  if (value.includes("@")) return null;
  if (value.toLowerCase().startsWith("whatsapp ")) return null;
  return value;
}

function collectCandidates(payload: Record<string, unknown>): Record<string, unknown>[] {
  const out: Record<string, unknown>[] = [];
  const data = payload.data;
  if (Array.isArray(data)) {
    for (const item of data) {
      const r = asRecord(item);
      if (r) out.push(r);
    }
  } else {
    const d = asRecord(data);
    if (d) {
      if (d.key || d.message) out.push(d);
      else if (Array.isArray(d.messages)) {
        for (const m of d.messages) {
          const r = asRecord(m);
          if (r) out.push(r);
        }
      }
    }
  }
  if (!out.length && (payload.key || payload.message)) out.push(payload);
  return out;
}

export function extractInboundMessages(payload: unknown): NormalizedInbound[] {
  const root = asRecord(payload);
  if (!root) return [];
  const instance =
    String(root.instance ?? root.instanceName ?? process.env.EVOLUTION_INSTANCE ?? "facilcar");
  const results: NormalizedInbound[] = [];
  for (const item of collectCandidates(root)) {
    const key = asRecord(item.key) ?? {};
    const message = asRecord(item.message);
    const fromMe = Boolean(key.fromMe ?? item.fromMe);
    const remoteJid = String(key.remoteJid ?? item.remoteJid ?? "") || null;
    const remoteJidAltRaw = key.remoteJidAlt ?? item.remoteJidAlt;
    const remoteJidAlt =
      remoteJidAltRaw != null && String(remoteJidAltRaw).trim()
        ? String(remoteJidAltRaw)
        : null;
    const messageId = String(key.id ?? item.id ?? "");
    if (!messageId) continue;
    const text = extractText(message);
    const media = detectMedia(message);
    const tsRaw = item.messageTimestamp ?? key.messageTimestamp ?? root.date_time;
    let waTimestamp: Date | null = null;
    if (typeof tsRaw === "number") waTimestamp = new Date(tsRaw * (tsRaw < 1e12 ? 1000 : 1));
    else if (typeof tsRaw === "string" && tsRaw) {
      const n = Number(tsRaw);
      waTimestamp = Number.isFinite(n)
        ? new Date(n * (n < 1e12 ? 1000 : 1))
        : new Date(tsRaw);
      if (Number.isNaN(waTimestamp.getTime())) waTimestamp = null;
    }
    results.push({
      instance,
      messageId,
      remoteJid,
      remoteJidAlt,
      fromMe,
      messageType: media.messageType,
      waTimestamp,
      text,
      hasMedia: media.hasMedia,
      mediaRef: media.mediaRef,
      rawMessage: message,
      pushName: fromMe ? null : extractWhatsAppPushName(item),
    });
  }
  return results;
}
