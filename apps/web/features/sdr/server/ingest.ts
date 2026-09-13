import type { MessageContentType, Prisma } from "@prisma/client";
import { extractInboundMessages } from "@/features/catalog-import/server/evolution-parse";
import { upgradeCustomerDisplayNameByPhone } from "@/features/customer/server/upsert";
import {
  classifyFromMeProvenance,
  pendingBotReservationWhere,
  shouldAssumeHumanFromMe,
} from "./fromme-provenance";
import { humanFromMeOwnershipCas } from "./human-from-me-cas";
import { prisma } from "@/lib/db";
import { isGroupJid, sdrPreferredPhone } from "./jid-guard";
import { extractSdrQuotedContext } from "./quoted-context";

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
  let inboundHandled = 0;
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
      select: { id: true, conversationId: true, isBotSent: true },
    });
    // Dedupe is instance-scoped (instanceName + providerMessageId). A bot
    // echo or a second Evolution delivery of the same id must not assume
    // this thread again, and must not touch another conversation.
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
        ...(!msg.fromMe ? { contextRevision: 1 } : {}),
      },
      update: {
        lastMessageAt: lastAt,
        ...(!msg.fromMe ? { contextRevision: { increment: 1 } } : {}),
      },
    });
    conversationId = conversation.id;

    // Provenance: Assumir is HUMAN_CONFIRMED. fromMe / real id / missing bot
    // row / divergent text are AMBIGUOUS and never flip ownership.
    const pendingWhere = pendingBotReservationWhere({
      conversationId: conversation.id,
      instanceName: msg.instance,
      text: msg.text,
    });
    let pendingReservation = false;
    let textMatchesReservation: boolean | null = null;
    if (msg.fromMe && pendingWhere) {
      const pending = await prisma.message.findFirst({
        where: pendingWhere,
        orderBy: { createdAt: "asc" },
        select: { id: true },
      });
      if (pending) {
        try {
          await prisma.message.update({
            where: { id: pending.id },
            data: { providerMessageId: msg.messageId },
          });
        } catch {
          // Unique on instanceName+providerMessageId: already correlated.
        }
        deduped++;
        messageIds.push(pending.id);
        continue;
      }
    }
    if (msg.fromMe) {
      const openReservation = await prisma.message.findFirst({
        where: {
          conversationId: conversation.id,
          instanceName: msg.instance,
          isBotSent: true,
          providerMessageId: { startsWith: "bot-pending-" },
        },
        orderBy: { createdAt: "asc" },
        select: { id: true, text: true },
      });
      if (openReservation) {
        pendingReservation = true;
        textMatchesReservation =
          (openReservation.text ?? "").trim() === (msg.text ?? "").trim();
      }
    }
    const classification = classifyFromMeProvenance({
      fromMe: msg.fromMe,
      providerMessageId: msg.messageId,
      existingIsBotSent: false,
      knownBotProviderId: false,
      pendingBotReservation: pendingReservation,
      textMatchesReservation,
    });
    const assumeHuman = shouldAssumeHumanFromMe(classification);
    if (assumeHuman) {
      const cas = humanFromMeOwnershipCas({
        conversationId: conversation.id,
        ownershipRevision: conversation.ownershipRevision,
        botStatus: conversation.botStatus,
        handoffAt: conversation.handoffAt,
        lastAt,
      });
      if (cas) {
        await prisma.conversation.updateMany({
          where: cas.where,
          data: cas.data,
        });
      }
    }

    // For AUDIO/IMAGE/DOCUMENT messages, store the media reference in
    // turnFactsJson so the Python worker can download and process the media.
    // The "_sdr_media" key is read by the orchestrator's audio enrichment path.
    let mediaInitJson: Prisma.InputJsonValue | undefined = undefined;
    const turnFactsBase: Record<string, Prisma.InputJsonValue> = {};

    if (msg.hasMedia && msg.mediaRef) {
      turnFactsBase["_sdr_media"] = {
        key: {
          remoteJid: msg.remoteJid ?? null,
          fromMe: msg.fromMe,
          id: msg.messageId,
        },
        message: (msg.rawMessage ?? {}) as Prisma.InputJsonValue,
      };
    }

    // When the customer used WhatsApp reply feature, store quoted stanza +
    // structured metadata. Prefer SDR-owned extraction (image/document/video
    // contextInfo) over catalog-import's extendedText-only stanza id.
    if (!msg.fromMe) {
      const quoted = extractSdrQuotedContext(msg.rawMessage);
      const stanzaId = quoted?.stanzaId ?? msg.quotedStanzaId;
      if (stanzaId) {
        turnFactsBase["_sdr_quoted_id"] = stanzaId;
        if (quoted) {
          turnFactsBase["_sdr_quoted"] = {
            stanzaId: quoted.stanzaId,
            quotedType: quoted.quotedType,
            quotedText: quoted.quotedText,
          };
        }
      }
    }

    if (msg.fromMe) {
      turnFactsBase["_sdr_fromme"] = {
        authorship: classification.authorship,
        kind: classification.kind,
        reason: classification.reason,
      };
    }

    if (Object.keys(turnFactsBase).length > 0) {
      mediaInitJson = turnFactsBase;
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
        isHumanSent: assumeHuman,
        isBotSent: classification.kind === "bot_echo",
        processingStatus: msg.fromMe ? "DONE" : "PENDING",
        createdAt: lastAt,
        ...(mediaInitJson !== undefined ? { turnFactsJson: mediaInitJson } : {}),
      } satisfies Prisma.MessageUncheckedCreateInput,
    });

    messageIds.push(created.id);
    handled++;
    if (!msg.fromMe) {
      inboundHandled++;
      if (msg.pushName) {
        await upgradeCustomerDisplayNameByPhone(msg.pushName, phone);
      }
      markSdrDebounce(phone);
    }
  }

  if (handled === 0 && ignored > 0 && deduped === 0 && !reason) {
    reason = "ignored";
  }

  // fromMe (bot echo or human seller) must not wake process_turn. Worker
  // already claims only fromMe=false PENDING rows; skip the notify too so a
  // human bubble cannot start a concurrent auto-reply.
  if (inboundHandled > 0) {
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
