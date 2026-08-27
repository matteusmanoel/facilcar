import { randomUUID } from "node:crypto";
import { hostname } from "node:os";
import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";

export function getLockTimeoutMs(): number {
  const n = Number(process.env.CATALOG_IMPORT_LOCK_TIMEOUT_MS ?? "300000");
  return Number.isFinite(n) && n > 0 ? n : 300_000;
}

export function makeWorkerId(): string {
  return `${hostname()}:${process.pid}:${randomUUID().slice(0, 8)}`;
}

export async function recoverAbandonedLocks(): Promise<number> {
  const cutoff = new Date(Date.now() - getLockTimeoutMs());
  const res = await prisma.catalogImportItem.updateMany({
    where: {
      status: "PROCESSING",
      vehicleId: null,
      lockedAt: { lt: cutoff },
    },
    data: { status: "READY", lockedAt: null, lockedBy: null },
  });
  return res.count;
}

export async function claimReadyItem(workerId: string): Promise<string | null> {
  // In inspect mode, skip items already parsed so we don't reclaim the same READY forever.
  const where =
    process.env.CATALOG_IMPORT_MODE === "inspect"
      ? { status: "READY" as const, parsedJson: { equals: Prisma.DbNull } }
      : { status: "READY" as const };

  const candidate = await prisma.catalogImportItem.findFirst({
    where,
    orderBy: { createdAt: "asc" },
    select: { id: true },
  });
  if (!candidate) return null;

  const updated = await prisma.catalogImportItem.updateMany({
    where: { id: candidate.id, status: "READY" },
    data: {
      status: "PROCESSING",
      lockedBy: workerId,
      lockedAt: new Date(),
      attemptCount: { increment: 1 },
      lastAttemptAt: new Date(),
    },
  });
  if (updated.count !== 1) return null;
  return candidate.id;
}

export async function claimItemById(itemId: string, workerId: string): Promise<boolean> {
  const item = await prisma.catalogImportItem.findUnique({ where: { id: itemId } });
  if (!item) return false;
  if (item.status === "IMPORTED") return false;

  await prisma.catalogImportItem.update({
    where: { id: itemId },
    data: {
      status: "READY",
      lockedAt: null,
      lockedBy: null,
    },
  });

  const updated = await prisma.catalogImportItem.updateMany({
    where: { id: itemId, status: "READY" },
    data: {
      status: "PROCESSING",
      lockedBy: workerId,
      lockedAt: new Date(),
      attemptCount: { increment: 1 },
      lastAttemptAt: new Date(),
      error: null,
    },
  });
  return updated.count === 1;
}
