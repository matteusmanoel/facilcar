#!/usr/bin/env npx tsx
/**
 * Watch CatalogImportEvent for real WhatsApp traffic (Fase 0).
 * Usage: cd apps/web && npx tsx scripts/catalog-import-watch.ts [minutes]
 */
import { config } from "dotenv";
import { resolve } from "node:path";

config({ path: resolve(process.cwd(), ".env") });
config({ path: resolve(process.cwd(), ".env.local"), override: true });

const minutes = Number(process.argv[2] || "10");
const deadline = Date.now() + minutes * 60_000;
const seen = new Set<string>();

async function getPrisma() {
  const mod = await import("../lib/db");
  const prisma = (mod as { prisma?: unknown }).prisma ?? (mod as { default?: { prisma?: unknown } }).default?.prisma;
  if (!prisma) throw new Error("prisma export not found");
  return prisma as import("@prisma/client").PrismaClient;
}

async function tick(prisma: import("@prisma/client").PrismaClient) {
  const events = await prisma.catalogImportEvent.findMany({
    orderBy: { createdAt: "desc" },
    take: 80,
    select: {
      id: true,
      messageId: true,
      remoteJid: true,
      messageType: true,
      textKind: true,
      text: true,
      hasMedia: true,
      processingStatus: true,
      sequence: true,
      createdAt: true,
      error: true,
    },
  });

  for (const e of events) {
    if (e.messageId.startsWith("t-")) continue;
    if (seen.has(e.id)) continue;
    seen.add(e.id);
    console.log(
      JSON.stringify({
        new: true,
        sequence: e.sequence,
        messageType: e.messageType,
        textKind: e.textKind,
        hasMedia: e.hasMedia,
        remoteJid: e.remoteJid,
        status: e.processingStatus,
        text: (e.text || "").slice(0, 140),
        error: e.error,
        at: e.createdAt,
      }),
    );
  }

  const real = events.filter((e) => !e.messageId.startsWith("t-")).length;
  const vehicles = await prisma.vehicle.count();
  console.log(
    JSON.stringify({
      poll: true,
      realEvents: real,
      vehicles,
      mode: process.env.CATALOG_IMPORT_MODE,
      ts: new Date().toISOString(),
    }),
  );
  return real;
}

async function main() {
  console.log(
    JSON.stringify({
      watching: true,
      minutes,
      mode: process.env.CATALOG_IMPORT_MODE,
      allowlist: process.env.CATALOG_IMPORT_ALLOWED_JIDS,
      hint: "Send A-D from allowlisted catalog sender TO Evolution receiver",
    }),
  );
  const prisma = await getPrisma();
  while (Date.now() < deadline) {
    try {
      await tick(prisma);
    } catch (e) {
      console.log(JSON.stringify({ pollError: e instanceof Error ? e.message : String(e) }));
    }
    await new Promise((r) => setTimeout(r, 8000));
  }
  console.log(JSON.stringify({ watchingDone: true, seenReal: [...seen].length }));
  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
