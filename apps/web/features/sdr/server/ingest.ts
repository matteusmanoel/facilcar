import type { MessageContentType, Prisma } from "@prisma/client";
import { extractInboundMessages } from "@/features/catalog-import/server/evolution-parse";
import { prisma } from "@/lib/db";
import { isGroupJid, sdrPreferredPhone } from "./jid-guard";

export type IngestSdrResult = {
  ok: true;
  handled: number;
  ignored: number;
  deduped: number;
  reason?: string;
  conversationId?: string;
  messageIds?: string[];
};

function mapContentType(messageType: string | null): MessageContentType {
  switch (messageType) {
    case "conversation":
    case "extendedTextMessage":
      return "TEXT";
    case "imageMessage":
      return "IMAGE";
    case "videoMessage":
      return "VIDEO";
    case "documentMessage":
      return "DOCUMENT";
    case "audioMessage":
      return "AUDIO";
    case "stickerMessage":
      return "STICKER";
    default:
      return "UNKNOWN";
  }
}

function juliaEnabled(): boolean {
  const raw = (process.env.JULIA_ENABLED ?? "").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes";
}

function notifySdrApi(payload: unknown): void {
  if (!juliaEnabled()) return;
  const base = (process.env.SDR_API_URL ?? "").trim().replace(/\/$/, "");
  if (!base) return;
  const secret = process.env.SDR_WEBHOOK_SECRET ?? "";
  const url = `${base}/webhook/evolution`;
  void fetch(url, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(secret ? { "x-sdr-secret": secret } : {}),
    },
    body: JSON.stringify(payload ?? {}),
  }).catch((err) => {
    console.warn("[sdr] notify SDR_API_URL failed", err);
  });
}

function markSdrDebounce(phone: string): void {
  if (!juliaEnabled()) return;
  const base = (process.env.SDR_API_URL ?? "").trim().replace(/\/$/, "");
  if (!base) return;
  const secret = process.env.SDR_WEBHOOK_SECRET ?? "";
  void fetch(`${base}/internal/debounce`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(secret ? { "x-sdr-secret": secret } : {}),
    },
    body: JSON.stringify({ phone }),
  }).catch((err) => {
    console.warn("[sdr] mark debounce failed", err);
  });
}

export async function ingestSdrWebhook(payload: unknown): Promise<IngestSdrResult> {
  const messages = extractInboundMessages(payload);

  let handled = 0;
  let ignored = 0;
  let deduped = 0;
  let reason: string | undefined;
  let conversationId: string | undefined;
  const messageIds: string[] = [];

  for (const msg of messages) {
    if (isGroupJid(msg.remoteJid) || isGroupJid(msg.remoteJidAlt)) {
      ignored++;
      reason = "group_ignored";
      continue;
    }

    const phone = sdrPreferredPhone(msg.remoteJid, msg.remoteJidAlt);
    if (!phone) {
      ignored++;
      reason = reason ?? "missing_phone";
      continue;
    }

    const existing = await prisma.message.findUnique({
      where: {
        instanceName_providerMessageId: {
          instanceName: msg.instance,
          providerMessageId: msg.messageId,
        },
      },
      select: { id: true, conversationId: true },
    });
    if (existing) {
      deduped++;
      conversationId = conversationId ?? existing.conversationId;
      messageIds.push(existing.id);
      continue;
    }

    const lastAt = msg.waTimestamp ?? new Date();

    const conversation = await prisma.conversation.upsert({
      where: {
        instanceName_phone: {
          instanceName: msg.instance,
          phone,
        },
      },
      create: {
        instanceName: msg.instance,
        phone,
        lastMessageAt: lastAt,
      },
      update: {
        lastMessageAt: lastAt,
      },
    });
    conversationId = conversation.id;

    // Bot outbound must be pre-inserted with isBotSent=true + providerMessageId
    // before Evolution send; the echo then hits the dedupe branch above.
    // Any NEW fromMe without that pre-insert is treated as a human seller.
    let isHumanSent = false;
    if (msg.fromMe) {
      isHumanSent = true;
      // Never auto-humanize if thread already past handoff confirmation only —
      // still mark HUMAN_ACTIVE so Julia stays silent on seller typing.
      if (
        conversation.botStatus !== "HUMAN_ACTIVE" &&
        conversation.botStatus !== "HUMAN_CLOSED"
      ) {
        await prisma.conversation.update({
          where: { id: conversation.id },
          data: {
            botStatus: "HUMAN_ACTIVE",
            handoffAt: conversation.handoffAt ?? lastAt,
          },
        });
      }
    }

    // For AUDIO/IMAGE/DOCUMENT messages, store the media reference in
    // turnFactsJson so the Python worker can download and process the media.
    // The "_sdr_media" key is read by the orchestrator's audio enrichment path.
    let mediaInitJson: Prisma.InputJsonValue | undefined = undefined;
    if (msg.hasMedia && msg.mediaRef) {
      mediaInitJson = {
        _sdr_media: {
          key: {
            remoteJid: msg.remoteJid ?? null,
            fromMe: msg.fromMe,
            id: msg.messageId,
          },
          message: (msg.rawMessage ?? {}) as Prisma.InputJsonValue,
        },
      };
    }

    // Extract MIME type from mediaRef when available (e.g., audio/ogg).
    let mediaMimeType: string | null = null;
    if (msg.mediaRef && typeof msg.mediaRef === "object") {
      const msgBlock = (msg.mediaRef as Record<string, unknown>).message;
      if (msgBlock && typeof msgBlock === "object") {
        const mime = (msgBlock as Record<string, unknown>).mimetype;
        if (typeof mime === "string") mediaMimeType = mime;
      }
    }

    const created = await prisma.message.create({
      data: {
        conversationId: conversation.id,
        providerMessageId: msg.messageId,
        instanceName: msg.instance,
        direction: msg.fromMe ? "OUTBOUND" : "INBOUND",
        contentType: mapContentType(msg.messageType),
        text: msg.text,
        mediaMimeType,
        fromMe: msg.fromMe,
        isHumanSent,
        isBotSent: false,
        processingStatus: "PENDING",
        createdAt: lastAt,
        ...(mediaInitJson !== undefined ? { turnFactsJson: mediaInitJson } : {}),
      } satisfies Prisma.MessageUncheckedCreateInput,
    });

    messageIds.push(created.id);
    handled++;
    if (!msg.fromMe) {
      markSdrDebounce(phone);
    }
  }

  if (handled === 0 && ignored > 0 && deduped === 0 && !reason) {
    reason = "ignored";
  }

  if (handled > 0) {
    notifySdrApi(payload);
  }

  return {
    ok: true,
    handled,
    ignored,
    deduped,
    ...(reason ? { reason } : {}),
    ...(conversationId ? { conversationId } : {}),
    ...(messageIds.length ? { messageIds } : {}),
  };
}
