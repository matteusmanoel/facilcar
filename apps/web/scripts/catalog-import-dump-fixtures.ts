#!/usr/bin/env node
/**
 * Dump sanitized CatalogImportEvent payloads to fixtures for Fase 0.
 * Usage: node --import tsx apps/web/scripts/catalog-import-dump-fixtures.ts
 * or: cd apps/web && npx tsx scripts/catalog-import-dump-fixtures.ts
 */
import { config } from "dotenv";
import { resolve } from "node:path";
import { mkdirSync, writeFileSync } from "node:fs";

config({ path: resolve(process.cwd(), ".env") });
config({ path: resolve(process.cwd(), ".env.local"), override: true });

const REDACT = "[REDACTED]";
const SENSITIVE =
  /^(base64|data|filebase64|mediakey|mediakeyiv|fileencsha256|filesha256|jpegthumbnail|token|apikey|authorization|secret|password)$/i;

function walk(value: unknown, depth = 0): unknown {
  if (depth > 14) return "[TRUNCATED_DEPTH]";
  if (Array.isArray(value)) return value.map((v) => walk(v, depth + 1));
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (SENSITIVE.test(k)) {
        out[k] = REDACT;
        continue;
      }
      if (typeof v === "string" && v.length > 400 && /^[A-Za-z0-9+/=]+$/.test(v.slice(0, 80))) {
        out[k] = REDACT;
        continue;
      }
      out[k] = walk(v, depth + 1);
    }
    return out;
  }
  return value;
}

async function main() {
  const { prisma } = await import("../lib/db");
  const outDir = resolve(process.cwd(), "features/catalog-import/fixtures");
  mkdirSync(outDir, { recursive: true });

  const events = await prisma.catalogImportEvent.findMany({
    orderBy: [{ sequence: "asc" }],
    take: 200,
  });

  const summary = events.map((e) => ({
    id: e.id,
    sequence: e.sequence,
    messageId: e.messageId,
    remoteJid: e.remoteJid,
    messageType: e.messageType,
    textKind: e.textKind,
    hasMedia: e.hasMedia,
    processingStatus: e.processingStatus,
    textPreview: (e.text || "").slice(0, 120),
    createdAt: e.createdAt,
    error: e.error,
  }));

  writeFileSync(resolve(outDir, "fase0-events-summary.json"), JSON.stringify(summary, null, 2));

  for (const e of events) {
    // skip synthetic test message ids
    if (e.messageId.startsWith("t-")) continue;
    const sanitized = {
      caseHint: null as string | null,
      instance: e.instance,
      messageId: e.messageId,
      remoteJid: e.remoteJid,
      fromMe: e.fromMe,
      messageType: e.messageType,
      textKind: e.textKind,
      text: e.text,
      hasMedia: e.hasMedia,
      mediaRef: walk(e.mediaRef),
      waTimestamp: e.waTimestamp,
      sequence: e.sequence,
      rawPayload: walk(e.rawPayload),
      payloadHash: e.payloadHash,
    };
    const t = (e.text || "").toLowerCase();
    if (e.messageType?.includes("product") || /productmessage|productsnapshot/i.test(JSON.stringify(e.rawPayload))) {
      sanitized.caseHint = "A-product";
    } else if (e.hasMedia && e.text) {
      sanitized.caseHint = "B-image-caption";
    } else if (e.hasMedia && !e.text) {
      sanitized.caseHint = "C-media-only";
    } else if (t) {
      sanitized.caseHint = "text";
    }
    const name = `event-${String(e.sequence).padStart(4, "0")}-${(sanitized.caseHint || "misc").replace(/[^a-z0-9-]/gi, "")}.json`;
    writeFileSync(resolve(outDir, name), JSON.stringify(sanitized, null, 2));
  }

  const vehicles = await prisma.vehicle.count();
  console.log(
    JSON.stringify(
      {
        mode: process.env.CATALOG_IMPORT_MODE,
        events: events.length,
        realEvents: events.filter((e) => !e.messageId.startsWith("t-")).length,
        vehicles,
        outDir,
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
