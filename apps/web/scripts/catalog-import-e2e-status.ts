#!/usr/bin/env npx tsx
import { config } from "dotenv";
import { resolve } from "node:path";

config({ path: resolve(process.cwd(), ".env") });
config({ path: resolve(process.cwd(), ".env.local"), override: true });

async function main() {
  const { prisma } = await import("../lib/db");
  const { groupPendingEvents, softCloseIdleItems } = await import(
    "../features/catalog-import/server/grouper"
  );
  const { runWorkerTick } = await import("../features/catalog-import/server/worker");

  process.env.CATALOG_IMPORT_MODE = process.env.CATALOG_IMPORT_MODE || "inspect";

  await groupPendingEvents();
  await softCloseIdleItems();
  const worker = await runWorkerTick();

  const real = await prisma.catalogImportEvent.findMany({
    where: { NOT: { messageId: { startsWith: "t-" } } },
    orderBy: { createdAt: "desc" },
    take: 20,
    select: {
      messageId: true,
      remoteJid: true,
      fromMe: true,
      messageType: true,
      textKind: true,
      processingStatus: true,
      hasMedia: true,
      mediaStatus: true,
      importItemId: true,
      sequence: true,
      createdAt: true,
      text: true,
      error: true,
    },
  });

  const items = await prisma.catalogImportItem.findMany({
    where: {
      OR: [
        { sessionKey: { contains: "554588230845" } },
        { sessionKey: { contains: "5545988230845" } },
      ],
    },
    orderBy: { createdAt: "desc" },
    include: {
      events: {
        select: {
          messageId: true,
          fromMe: true,
          textKind: true,
          processingStatus: true,
        },
      },
      mediaAssets: { select: { status: true, sortOrder: true } },
    },
  });

  console.log(
    JSON.stringify(
      {
        mode: process.env.CATALOG_IMPORT_MODE,
        allowlist: process.env.CATALOG_IMPORT_ALLOWED_JIDS,
        vehicles: await prisma.vehicle.count(),
        worker,
        realEvents: real.map((e) => ({
          ...e,
          text: (e.text || "").slice(0, 120),
        })),
        trackerItems: items.map((i) => ({
          id: i.id,
          status: i.status,
          vehicleId: i.vehicleId,
          attemptCount: i.attemptCount,
          sourceMessageId: i.sourceMessageId,
          rawText: (i.rawText || "").slice(0, 160),
          parsedJson: i.parsedJson,
          error: i.error,
          events: i.events,
          media: i.mediaAssets,
        })),
      },
      null,
      2,
    ),
  );

  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
