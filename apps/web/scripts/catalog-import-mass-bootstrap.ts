#!/usr/bin/env npx tsx
/**
 * Mass-import bootstrap:
 * 1) Skip synthetic/replay staging items
 * 2) Drain READY real items with MODE=import
 * 3) Print summary
 */
import { config } from "dotenv";
import { resolve } from "node:path";

config({ path: resolve(process.cwd(), ".env") });
config({ path: resolve(process.cwd(), ".env.local"), override: true });

process.env.CATALOG_IMPORT_MODE = "import";

function isSynthetic(sourceMessageId: string | null | undefined) {
  const id = sourceMessageId || "";
  return (
    id.startsWith("t-") ||
    id.startsWith("REPLAY-") ||
    id.startsWith("SYN-") ||
    id.startsWith("TESTE")
  );
}

async function main() {
  const { prisma } = await import("../lib/db");
  const { groupPendingEvents, softCloseIdleItems } = await import(
    "../features/catalog-import/server/grouper"
  );
  const { retryItem, runWorkerTick } = await import("../features/catalog-import/server/worker");

  await groupPendingEvents();
  await softCloseIdleItems();

  const skip = await prisma.catalogImportItem.updateMany({
    where: {
      status: { in: ["READY", "FAILED", "COLLECTING"] },
      OR: [
        { sourceMessageId: { startsWith: "t-" } },
        { sourceMessageId: { startsWith: "REPLAY-" } },
        { sourceMessageId: { startsWith: "SYN-" } },
      ],
    },
    data: {
      status: "FAILED",
      error: "skipped_non_production_fixture",
      lockedAt: null,
      lockedBy: null,
    },
  });

  const ready = await prisma.catalogImportItem.findMany({
    where: { status: "READY", vehicleId: null },
    orderBy: { createdAt: "asc" },
    select: { id: true, sourceMessageId: true, rawText: true },
  });

  const results: Array<Record<string, unknown>> = [];
  for (const item of ready) {
    if (isSynthetic(item.sourceMessageId)) continue;
    try {
      await retryItem(item.id);
      const after = await prisma.catalogImportItem.findUnique({
        where: { id: item.id },
        select: { status: true, vehicleId: true, error: true, warnings: true },
      });
      results.push({
        id: item.id,
        src: item.sourceMessageId,
        ...after,
        raw: (item.rawText || "").slice(0, 80),
      });
    } catch (e) {
      results.push({
        id: item.id,
        src: item.sourceMessageId,
        error: e instanceof Error ? e.message : String(e),
      });
    }
  }

  // Drain a few more ticks for any newly closed COLLECTING items
  for (let i = 0; i < 5; i++) {
    const tick = await runWorkerTick();
    if (!tick.processed) break;
  }

  const drafts = await prisma.vehicle.findMany({
    where: { status: "DRAFT" },
    orderBy: { updatedAt: "desc" },
    take: 20,
    select: {
      id: true,
      title: true,
      slug: true,
      priceCash: true,
      model: true,
      _count: { select: { images: true } },
    },
  });

  console.log(
    JSON.stringify(
      {
        mode: process.env.CATALOG_IMPORT_MODE,
        skippedFixtures: skip.count,
        importedNow: results,
        draftVehicles: drafts.map((d) => ({
          id: d.id,
          title: d.title,
          slug: d.slug,
          model: d.model,
          priceCash: d.priceCash?.toString() ?? null,
          images: d._count.images,
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
