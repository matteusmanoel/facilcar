#!/usr/bin/env npx tsx
/**
 * One-shot smoke: force CATALOG_IMPORT_MODE=import for a single item.
 * Usage: npx tsx scripts/catalog-import-smoke-import.ts <itemId>
 */
import { config } from "dotenv";
import { resolve } from "node:path";

config({ path: resolve(process.cwd(), ".env") });
config({ path: resolve(process.cwd(), ".env.local"), override: true });

async function main() {
  const itemId = process.argv[2];
  if (!itemId) {
    console.error("Usage: catalog-import-smoke-import.ts <itemId>");
    process.exit(1);
  }
  // Must set AFTER dotenv — .env.local defaults to inspect for Fase 0.
  process.env.CATALOG_IMPORT_MODE = "import";
  console.log(
    JSON.stringify({
      mode: process.env.CATALOG_IMPORT_MODE,
      itemId,
      storage: !!(
        process.env.STORAGE_ENDPOINT &&
        process.env.STORAGE_BUCKET_NAME &&
        process.env.STORAGE_ACCESS_KEY
      ),
    }),
  );
  const { retryItem } = await import("../features/catalog-import/server/worker");
  await retryItem(itemId);

  const { prisma } = await import("../lib/db");
  const item = await prisma.catalogImportItem.findUnique({
    where: { id: itemId },
    include: {
      mediaAssets: { include: { blob: true } },
    },
  });
  const vehicle = item?.vehicleId
    ? await prisma.vehicle.findUnique({
        where: { id: item.vehicleId },
        include: { images: { orderBy: { sortOrder: "asc" }, take: 5 } },
      })
    : null;
  console.log(
    JSON.stringify(
      {
        item: item
          ? {
              id: item.id,
              status: item.status,
              vehicleId: item.vehicleId,
              error: item.error,
              warnings: item.warnings,
              media: item.mediaAssets.map((m) => ({
                status: m.status,
                error: m.error,
                blobKey: m.blob?.storageKey ?? null,
                sha: m.blob?.sha256?.slice(0, 12) ?? null,
              })),
            }
          : null,
        vehicle: vehicle
          ? {
              id: vehicle.id,
              status: vehicle.status,
              title: vehicle.title,
              slug: vehicle.slug,
              priceCash: vehicle.priceCash?.toString?.() ?? vehicle.priceCash,
              images: vehicle.images.map((img) => ({
                url: img.url,
                sortOrder: img.sortOrder,
              })),
            }
          : null,
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
