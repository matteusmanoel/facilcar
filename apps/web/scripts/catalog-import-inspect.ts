import { config } from "dotenv";
import { resolve } from "node:path";

config({ path: resolve(process.cwd(), ".env") });
config({ path: resolve(process.cwd(), ".env.local"), override: true });

async function main() {
  process.env.CATALOG_IMPORT_MODE = process.env.CATALOG_IMPORT_MODE || "inspect";
  const { prisma } = await import("../lib/db");
  const { groupPendingEvents, softCloseIdleItems } = await import(
    "../features/catalog-import/server/grouper"
  );
  const { runWorkerTick } = await import("../features/catalog-import/server/worker");

  const events = await prisma.catalogImportEvent.findMany({
    orderBy: { createdAt: "desc" },
    take: 20,
    select: {
      id: true,
      instance: true,
      messageId: true,
      remoteJid: true,
      textKind: true,
      text: true,
      hasMedia: true,
      processingStatus: true,
      sequence: true,
      error: true,
      createdAt: true,
    },
  });
  console.log(JSON.stringify({ mode: "inspect", recentEvents: events }, null, 2));

  await groupPendingEvents();
  await softCloseIdleItems();
  await runWorkerTick();

  const items = await prisma.catalogImportItem.findMany({
    orderBy: { createdAt: "desc" },
    take: 20,
    include: {
      events: { select: { messageId: true, textKind: true, sequence: true } },
      mediaAssets: { select: { id: true, status: true, sortOrder: true } },
    },
  });
  console.log(JSON.stringify({ items }, null, 2));
  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
