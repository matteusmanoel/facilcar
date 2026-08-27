import { prisma } from "@/lib/db";
import { sanitizePayload } from "./sanitize-payload";
import {
  parseAllowedJids,
  peerIdentityCandidates,
  isAnyJidAllowed,
  preferredPeerJid,
} from "./normalize-jid";
import { extractInboundMessages } from "./evolution-parse";
import { classifyEvent } from "./classify";

export type IngestResult = {
  ok: true;
  handled: number;
  ignored: number;
  deduped: number;
  eventIds: string[];
};

async function nextSequence(instance: string): Promise<number> {
  const last = await prisma.catalogImportEvent.findFirst({
    where: { instance },
    orderBy: { sequence: "desc" },
    select: { sequence: true },
  });
  return (last?.sequence ?? 0) + 1;
}

export async function ingestEvolutionWebhook(payload: unknown): Promise<IngestResult> {
  const allowed = parseAllowedJids(process.env.CATALOG_IMPORT_ALLOWED_JIDS);
  const messages = extractInboundMessages(payload);
  const { sanitized, truncated, payloadHash } = sanitizePayload(payload);

  let handled = 0;
  let ignored = 0;
  let deduped = 0;
  const eventIds: string[] = [];

  for (const msg of messages) {
    // Peer = chat counterpart. Inbound to Evolution: sender; outbound forward: destination.
    // Receiver is always the Evolution instance number — not listed here.
    const candidates = peerIdentityCandidates(msg.remoteJid, msg.remoteJidAlt);
    const jidNorm = preferredPeerJid(candidates);
    if (!isAnyJidAllowed(candidates, allowed)) {
      ignored++;
      continue;
    }

    const existing = await prisma.catalogImportEvent.findUnique({
      where: {
        instance_messageId: { instance: msg.instance, messageId: msg.messageId },
      },
    });
    if (existing) {
      if (existing.payloadHash !== payloadHash) {
        console.warn(
          JSON.stringify({
            stage: "INGEST",
            warning: "payload_hash_mismatch",
            instance: msg.instance,
            messageId: msg.messageId,
          }),
        );
      }
      deduped++;
      eventIds.push(existing.id);
      continue;
    }

    const textKind = classifyEvent({
      text: msg.text,
      hasMedia: msg.hasMedia,
      rawPayload: sanitized,
    });

    let processingStatus: "RECEIVED" | "IGNORED" = "RECEIVED";
    let error: string | null = null;
    if (textKind === "UNKNOWN" && !msg.hasMedia) {
      processingStatus = "IGNORED";
      error = "unknown_classification";
      ignored++;
    } else {
      handled++;
    }

    const sequence = await nextSequence(msg.instance);
    const created = await prisma.catalogImportEvent.create({
      data: {
        instance: msg.instance,
        messageId: msg.messageId,
        remoteJid: jidNorm || null,
        fromMe: msg.fromMe,
        messageType: msg.messageType,
        textKind,
        waTimestamp: msg.waTimestamp,
        sequence,
        payloadHash,
        rawPayload: sanitized as object,
        rawPayloadTruncated: truncated,
        text: msg.text,
        hasMedia: msg.hasMedia,
        mediaRef: msg.mediaRef ? (msg.mediaRef as object) : undefined,
        mediaStatus: msg.hasMedia ? "PENDING" : null,
        processingStatus,
        error,
      },
    });
    eventIds.push(created.id);
  }

  return { ok: true, handled, ignored, deduped, eventIds };
}
