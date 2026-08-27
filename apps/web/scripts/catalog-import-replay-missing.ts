#!/usr/bin/env npx tsx
/**
 * Replay recent Evolution inbound messages into the webhook if missing from staging.
 */
import { config } from "dotenv";
import { resolve } from "node:path";

config({ path: resolve(process.cwd(), ".env") });
config({ path: resolve(process.cwd(), ".env.local"), override: true });

async function main() {
  const base = process.env.EVOLUTION_API_URL?.replace(/\/$/, "") || "http://localhost:8081";
  const key = process.env.EVOLUTION_API_KEY;
  const instance = process.env.EVOLUTION_INSTANCE || "facilcar";
  const secret = process.env.CATALOG_IMPORT_SECRET;
  if (!key || !secret) throw new Error("missing EVOLUTION_API_KEY or CATALOG_IMPORT_SECRET");

  const { prisma } = await import("../lib/db");

  const res = await fetch(`${base}/chat/findMessages/${instance}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: key },
    body: JSON.stringify({ where: { key: { remoteJid: "245861426659479@lid" } } }),
  });
  if (!res.ok) throw new Error(`findMessages ${res.status}`);
  const body = (await res.json()) as {
    messages?: { records?: Array<Record<string, unknown>> };
  };
  const records = body.messages?.records ?? [];

  let posted = 0;
  let skipped = 0;
  let deduped = 0;

  for (const m of records) {
    const keyObj = (m.key ?? {}) as Record<string, unknown>;
    if (keyObj.fromMe) {
      skipped++;
      continue;
    }
    const messageId = String(keyObj.id ?? "");
    if (!messageId) continue;
    const existing = await prisma.catalogImportEvent.findUnique({
      where: { instance_messageId: { instance, messageId } },
      select: { id: true },
    });
    if (existing) {
      deduped++;
      continue;
    }

    const payload = {
      event: "messages.upsert",
      instance,
      data: {
        key: keyObj,
        pushName: m.pushName,
        message: m.message,
        messageType: m.messageType,
        messageTimestamp: m.messageTimestamp,
      },
    };
    const wr = await fetch("http://127.0.0.1:3000/api/webhooks/evolution", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${secret}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const text = await wr.text();
    console.log(JSON.stringify({ messageId, status: wr.status, body: text.slice(0, 200) }));
    posted++;
  }

  console.log(JSON.stringify({ posted, skippedFromMe: skipped, alreadyInDb: deduped, scanned: records.length }));
  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
