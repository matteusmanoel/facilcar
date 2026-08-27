import { prisma } from "@/lib/db";
import { groupPendingEvents, softCloseIdleItems } from "./grouper";
import { claimReadyItem, claimItemById, makeWorkerId, recoverAbandonedLocks } from "./claim";
import { deterministicParseFromText, type VehicleImportInput } from "./classify";
import { openaiExtractVehicle } from "./openai-extract";
import { processItemMedia } from "./evolution-media";
import { createDraftFromImport } from "./create-draft";

function log(stage: string, data: Record<string, unknown>) {
  console.log(JSON.stringify({ stage, ts: new Date().toISOString(), ...data }));
}

function needsOpenAI(input: VehicleImportInput): boolean {
  const missingCritical =
    !input.brand || !input.model || !input.priceCash || input.missingFields.length > 4;
  return missingCritical && !!process.env.OPENAI_API_KEY;
}

export async function parseItem(itemId: string): Promise<VehicleImportInput> {
  const item = await prisma.catalogImportItem.findUnique({ where: { id: itemId } });
  if (!item) throw new Error("item_not_found");
  if (item.parsedJson && process.env.CATALOG_IMPORT_FORCE_REPARSE !== "1") {
    return item.parsedJson as VehicleImportInput;
  }
  const rawText = item.rawText?.trim() || "";
  let parsed = deterministicParseFromText(rawText);
  if (needsOpenAI(parsed) && rawText) {
    log("OPENAI", { itemId, workerId: null });
    const ai = await openaiExtractVehicle(rawText);
    parsed = {
      ...ai,
      source: parsed.brand || parsed.model ? "hybrid" : "openai",
      warnings: [...parsed.warnings, ...ai.warnings],
      missingFields: ai.missingFields,
    };
  }
  await prisma.catalogImportItem.update({
    where: { id: itemId },
    data: { parsedJson: parsed as object },
  });
  return parsed;
}

export async function processClaimedItem(itemId: string, workerId: string): Promise<void> {
  const started = Date.now();
  try {
    log("PARSE", { itemId, workerId });
    await parseItem(itemId);

    // Fase 0 / inspect: staging + parse only — no Storage upload, no Vehicle/VehicleImage.
    if (process.env.CATALOG_IMPORT_MODE === "inspect") {
      log("COMPLETE", {
        itemId,
        workerId,
        mode: "inspect",
        durationMs: Date.now() - started,
        note: "skip_media_and_create_draft",
      });
      await prisma.catalogImportItem.update({
        where: { id: itemId },
        data: { status: "READY", lockedAt: null, lockedBy: null },
      });
      return;
    }

    log("MEDIA_DOWNLOAD", { itemId, workerId });
    const media = await processItemMedia(itemId);

    if (media.warnings.length) {
      const item = await prisma.catalogImportItem.findUnique({ where: { id: itemId } });
      await prisma.catalogImportItem.update({
        where: { id: itemId },
        data: { warnings: [...(item?.warnings ?? []), ...media.warnings] },
      });
    }

    log("CREATE_DRAFT", { itemId, workerId });
    const result = await createDraftFromImport(itemId);
    log("COMPLETE", {
      itemId,
      workerId,
      vehicleId: result.vehicleId,
      status: result.status,
      durationMs: Date.now() - started,
      attemptCount: undefined,
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "worker_error";
    log("FAILED", { itemId, workerId, error: msg, durationMs: Date.now() - started });
    await prisma.catalogImportItem.update({
      where: { id: itemId },
      data: {
        status: "FAILED",
        error: msg.slice(0, 500),
        lockedAt: null,
        lockedBy: null,
      },
    });
  }
}

export async function runWorkerTick(workerId = makeWorkerId()): Promise<{
  recovered: number;
  grouped: number;
  closed: number;
  processed: string | null;
}> {
  const recovered = await recoverAbandonedLocks();
  const { grouped } = await groupPendingEvents();
  const closed = await softCloseIdleItems();
  const itemId = await claimReadyItem(workerId);
  if (itemId) await processClaimedItem(itemId, workerId);
  return { recovered, grouped, closed, processed: itemId };
}

export async function retryItem(itemId: string): Promise<void> {
  const workerId = makeWorkerId();
  const item = await prisma.catalogImportItem.findUnique({ where: { id: itemId } });
  if (!item) throw new Error("item_not_found");
  if (item.status === "IMPORTED") {
    log("COMPLETE", { itemId, workerId, note: "already_imported", vehicleId: item.vehicleId });
    return;
  }
  const ok = await claimItemById(itemId, workerId);
  if (!ok) throw new Error("claim_failed");
  await processClaimedItem(itemId, workerId);
}

export async function runWorkerLoop(opts?: { intervalMs?: number; once?: boolean }) {
  const workerId = makeWorkerId();
  const intervalMs = opts?.intervalMs ?? 2000;
  log("CLAIM", { workerId, note: "worker_start" });
  for (;;) {
    try {
      await runWorkerTick(workerId);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      log("FAILED", { workerId, error: msg, note: "tick_error_retry" });
      // Pooler/transient DB drops should not kill the mass-import loop.
      await new Promise((r) => setTimeout(r, Math.max(intervalMs, 5000)));
    }
    if (opts?.once) break;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}
