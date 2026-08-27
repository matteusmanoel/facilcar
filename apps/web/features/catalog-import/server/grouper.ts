import { prisma } from "@/lib/db";
import { buildSessionKey } from "./normalize-jid";
import type { CatalogTextKind } from "@prisma/client";

export function getIdleMs(): number {
  const n = Number(process.env.CATALOG_IMPORT_IDLE_MS ?? "45000");
  return Number.isFinite(n) && n > 0 ? n : 45_000;
}

async function attachEventToItem(opts: {
  eventId: string;
  itemId: string;
  text: string | null;
  hasMedia: boolean;
  sequence: number;
  appendText: boolean;
}) {
  const item = await prisma.catalogImportItem.findUnique({ where: { id: opts.itemId } });
  if (!item) return;

  let rawText = item.rawText ?? "";
  if (opts.appendText && opts.text?.trim()) {
    rawText = rawText ? `${rawText}\n${opts.text.trim()}` : opts.text.trim();
  }

  await prisma.$transaction([
    prisma.catalogImportEvent.update({
      where: { id: opts.eventId },
      data: { importItemId: opts.itemId, processingStatus: "QUEUED" },
    }),
    prisma.catalogImportItem.update({
      where: { id: opts.itemId },
      data: { rawText: rawText || item.rawText },
    }),
  ]);

  if (opts.hasMedia) {
    await prisma.catalogMediaAsset.upsert({
      where: { eventId: opts.eventId },
      create: {
        importItemId: opts.itemId,
        eventId: opts.eventId,
        sortOrder: opts.sequence,
        status: "PENDING",
      },
      update: {
        importItemId: opts.itemId,
        sortOrder: opts.sequence,
      },
    });
  }
}

export async function groupPendingEvents(): Promise<{ grouped: number }> {
  const events = await prisma.catalogImportEvent.findMany({
    where: {
      processingStatus: "RECEIVED",
      importItemId: null,
    },
    orderBy: [{ instance: "asc" }, { sequence: "asc" }],
    take: 100,
  });

  let grouped = 0;
  for (const ev of events) {
    if (!ev.remoteJid) {
      await prisma.catalogImportEvent.update({
        where: { id: ev.id },
        data: { processingStatus: "IGNORED", error: "missing_remote_jid" },
      });
      continue;
    }
    const sessionKey = buildSessionKey(ev.instance, ev.remoteJid);
    const kind = (ev.textKind ?? "UNKNOWN") as CatalogTextKind;
    const open = await prisma.catalogImportItem.findFirst({
      where: { sessionKey, status: "COLLECTING" },
      orderBy: { createdAt: "desc" },
    });

    if (kind === "VEHICLE_START") {
      if (open) {
        await prisma.catalogImportItem.update({
          where: { id: open.id },
          data: { status: "READY" },
        });
      }
      const item = await prisma.catalogImportItem.create({
        data: {
          sessionKey,
          sourceMessageId: ev.messageId,
          rawText: ev.text ?? "",
          status: "COLLECTING",
        },
      });
      await attachEventToItem({
        eventId: ev.id,
        itemId: item.id,
        text: null,
        hasMedia: ev.hasMedia,
        sequence: ev.sequence,
        appendText: false,
      });
      if (ev.text?.trim()) {
        await prisma.catalogImportItem.update({
          where: { id: item.id },
          data: { rawText: ev.text.trim() },
        });
      }
      grouped++;
      continue;
    }

    if (kind === "CONTINUATION") {
      if (!open) {
        await prisma.catalogImportEvent.update({
          where: { id: ev.id },
          data: { processingStatus: "IGNORED", error: "continuation_without_open_item" },
        });
        continue;
      }
      await attachEventToItem({
        eventId: ev.id,
        itemId: open.id,
        text: ev.text,
        hasMedia: ev.hasMedia,
        sequence: ev.sequence,
        appendText: true,
      });
      grouped++;
      continue;
    }

    if (kind === "MEDIA_ONLY") {
      if (!open) {
        await prisma.catalogImportEvent.update({
          where: { id: ev.id },
          data: { processingStatus: "IGNORED", error: "orphan_media" },
        });
        continue;
      }
      await attachEventToItem({
        eventId: ev.id,
        itemId: open.id,
        text: null,
        hasMedia: true,
        sequence: ev.sequence,
        appendText: false,
      });
      grouped++;
      continue;
    }

    await prisma.catalogImportEvent.update({
      where: { id: ev.id },
      data: { processingStatus: "IGNORED", error: "unknown_classification" },
    });
  }

  return { grouped };
}

export async function softCloseIdleItems(): Promise<number> {
  const idleMs = getIdleMs();
  const collecting = await prisma.catalogImportItem.findMany({
    where: { status: "COLLECTING" },
    include: {
      events: { orderBy: { sequence: "desc" }, take: 1 },
    },
  });
  const now = Date.now();
  let closed = 0;
  for (const item of collecting) {
    const last = item.events[0];
    const lastAt = last?.createdAt?.getTime() ?? item.updatedAt.getTime();
    if (now - lastAt >= idleMs) {
      await prisma.catalogImportItem.update({
        where: { id: item.id },
        data: { status: "READY", idleClosedAt: new Date() },
      });
      closed++;
    }
  }
  return closed;
}
