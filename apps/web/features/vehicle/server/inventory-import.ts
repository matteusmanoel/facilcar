import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { slugify } from "@/features/vehicle/server/slug";
import { uniqueSlug } from "@/features/vehicle/server/unique-slug";
import { announcedPriceFromSnapshot } from "@/features/vehicle/lib/announced-price";
import { displayColorFromSnapshot } from "@/features/vehicle/lib/color";
import {
  reconcileInventorySnapshot,
  type DbVehicleForReconcile,
  type ReconcileOptions,
  type ReconcilePlan,
  type ReconcileRow,
  type SnapshotVehicle,
} from "@/features/vehicle/lib/inventory-reconcile";
import { normalizePlate, plateFinalFromPlate } from "@/features/vehicle/lib/plate";

const BRAND_DISPLAY: Record<string, string> = {
  audi: "Audi",
  chevrolet: "Chevrolet",
  citroen: "Citroën",
  fiat: "Fiat",
  ford: "Ford",
  honda: "Honda",
  hyundai: "Hyundai",
  peugeot: "Peugeot",
  renault: "Renault",
  toyota: "Toyota",
  volkswagen: "Volkswagen",
};

export type InventorySnapshotFile = {
  schemaVersion?: string;
  dataset?: { sourceFile?: string };
  vehicles: SnapshotVehicle[];
};

export function summarizePlan(plan: ReconcilePlan) {
  const count = (action: ReconcileRow["action"]) => plan.rows.filter((row) => row.action === action).length;
  const preserved = plan.rows.flatMap((row) =>
    row.patches.filter((patch) => patch.preservedBecauseNull).map((patch) => ({
      spreadsheetKey: row.spreadsheetKey,
      vehicleId: row.vehicleId,
      field: patch.field,
      kept: patch.from,
    })),
  );
  return {
    update: count("UPDATE"),
    create: count("CREATE"),
    conflict: count("CONFLICT"),
    draftAbsent: count("DRAFT_ABSENT"),
    preservedNullFields: preserved.length,
    preserved,
  };
}

export async function loadDbVehiclesForReconcile(): Promise<DbVehicleForReconcile[]> {
  const rows = await prisma.vehicle.findMany({
    include: { brand: { select: { name: true } } },
  });
  return rows.map((row) => ({
    id: row.id,
    status: row.status,
    title: row.title,
    brandName: row.brand.name,
    brandId: row.brandId,
    model: row.model,
    version: row.version,
    yearManufacture: row.yearManufacture,
    yearModel: row.yearModel,
    mileage: row.mileage,
    color: row.color,
    plate: row.plate,
    plateFinal: row.plateFinal,
    transmission: row.transmission,
    engineDisplacementLiters:
      row.engineDisplacementLiters != null ? Number(row.engineDisplacementLiters) : null,
    priceCash: row.priceCash != null ? Number(row.priceCash) : null,
    description: row.description,
    spreadsheetKey: row.spreadsheetKey,
    stockType: row.stockType,
  }));
}

function decimal(value: number | null | undefined): Prisma.Decimal | null {
  if (value == null) return null;
  return new Prisma.Decimal(value);
}

function brandDisplayName(raw: string): string {
  const key = raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
  return BRAND_DISPLAY[key] ?? raw.trim();
}

async function resolveBrandId(rawName: string): Promise<string> {
  const name = brandDisplayName(rawName);
  const slug = slugify(name);
  const existing = await prisma.brand.findFirst({
    where: { OR: [{ name: { equals: name, mode: "insensitive" } }, { slug }] },
  });
  if (existing) return existing.id;
  const created = await prisma.brand.create({
    data: { name, slug, isActive: true },
  });
  return created.id;
}

async function resolvePartnerIds(names: string[]): Promise<string[]> {
  const ids: string[] = [];
  for (const raw of names) {
    const name = raw.trim();
    if (!name) continue;
    const slug = slugify(name);
    const existing = await prisma.partner.findFirst({
      where: { OR: [{ name: { equals: name, mode: "insensitive" } }, { slug }] },
    });
    if (existing) {
      ids.push(existing.id);
      continue;
    }
    const created = await prisma.partner.create({
      data: { name, slug, isActive: true },
    });
    ids.push(created.id);
  }
  return ids;
}

function composeTitle(snapshot: SnapshotVehicle, brandName: string): string {
  return [brandName, snapshot.vehicle.model, snapshot.vehicle.version, snapshot.vehicle.year]
    .filter((part) => part != null && String(part).trim() !== "")
    .join(" ");
}

function snapshotPayload(row: ReconcileRow) {
  return {
    spreadsheetKey: row.spreadsheetKey,
    plateNormalized: row.plateNormalized,
    action: row.action,
    confidence: row.confidence,
    notes: row.notes,
    patches: row.patches,
    ownerNames: row.ownerNames,
    source: row.snapshot.source,
    rawDescription: row.snapshot.rawDescription,
  };
}

async function applyCreate(row: ReconcileRow, seenAt: Date): Promise<string> {
  const snapshot = row.snapshot;
  const brandId = await resolveBrandId(snapshot.vehicle.brand);
  const brand = await prisma.brand.findUniqueOrThrow({ where: { id: brandId } });
  const plate = normalizePlate(snapshot.vehicle.plate);
  const announced = announcedPriceFromSnapshot(snapshot.stockType, snapshot.pricing);
  const title = composeTitle(snapshot, brand.name);
  const slug = await uniqueSlug(slugify(title));
  const year = snapshot.vehicle.year;
  const vehicle = await prisma.vehicle.create({
    data: {
      slug,
      status: "PUBLISHED",
      type: "CAR",
      title,
      description: snapshot.rawDescription,
      sourceRawDescription: snapshot.rawDescription,
      brandId,
      model: snapshot.vehicle.model,
      version: snapshot.vehicle.version,
      yearManufacture: year,
      yearModel: year,
      mileage: snapshot.vehicle.mileageKm,
      transmission: snapshot.vehicle.transmission,
      engineDisplacementLiters: decimal(snapshot.vehicle.engineDisplacementLiters),
      color: displayColorFromSnapshot(snapshot.vehicle.color),
      plate,
      plateFinal: plateFinalFromPlate(plate),
      priceCash: decimal(announced),
      priceFipe: decimal(snapshot.pricing.fipe ?? null),
      priceRetailWithWarranty: decimal(snapshot.pricing.retailWithWarranty ?? null),
      priceRetailAsIs: decimal(snapshot.pricing.retailAsIs ?? null),
      priceOwnerAsking: decimal(snapshot.pricing.ownerAsking ?? null),
      stockType: snapshot.stockType,
      commercialHistory: snapshot.commercialHistory.normalized,
      commercialHistoryRaw: snapshot.commercialHistory.raw,
      spreadsheetKey: row.spreadsheetKey,
      lastSpreadsheetSeenAt: seenAt,
      publishedAt: new Date(),
    },
  });
  if (snapshot.stockType === "OWNED" && snapshot.ownership.owners.length > 0) {
    const partnerIds = await resolvePartnerIds(snapshot.ownership.owners);
    if (partnerIds.length) {
      await prisma.vehicleOwner.createMany({
        data: partnerIds.map((partnerId) => ({ vehicleId: vehicle.id, partnerId })),
      });
    }
  }
  return vehicle.id;
}

async function applyUpdate(row: ReconcileRow, seenAt: Date): Promise<string> {
  if (!row.vehicleId) throw new Error("update without vehicleId");
  const snapshot = row.snapshot;
  const current = await prisma.vehicle.findUniqueOrThrow({ where: { id: row.vehicleId } });
  const plate = normalizePlate(snapshot.vehicle.plate);
  const announced = announcedPriceFromSnapshot(snapshot.stockType, snapshot.pricing);
  const year = snapshot.vehicle.year;
  const data: Prisma.VehicleUpdateInput = {
    stockType: snapshot.stockType,
    spreadsheetKey: row.spreadsheetKey,
    lastSpreadsheetSeenAt: seenAt,
    sourceRawDescription: snapshot.rawDescription,
  };
  if (current.status === "DRAFT" || current.status === "PUBLISHED") {
    data.status = "PUBLISHED";
    if (current.status === "DRAFT") data.publishedAt = new Date();
  }
  if (snapshot.vehicle.model) data.model = snapshot.vehicle.model;
  if (snapshot.vehicle.version != null) data.version = snapshot.vehicle.version;
  if (year != null) {
    data.yearManufacture = year;
    data.yearModel = year;
  }
  if (snapshot.vehicle.mileageKm != null) data.mileage = snapshot.vehicle.mileageKm;
  const color = displayColorFromSnapshot(snapshot.vehicle.color);
  if (color) data.color = color;
  if (plate) {
    data.plate = plate;
    data.plateFinal = plateFinalFromPlate(plate);
  }
  if (snapshot.vehicle.transmission != null) data.transmission = snapshot.vehicle.transmission;
  if (snapshot.vehicle.engineDisplacementLiters != null) {
    data.engineDisplacementLiters = decimal(snapshot.vehicle.engineDisplacementLiters);
  }
  if (announced != null) data.priceCash = decimal(announced);
  if (snapshot.pricing.fipe != null) data.priceFipe = decimal(snapshot.pricing.fipe);
  if (snapshot.pricing.retailWithWarranty != null) {
    data.priceRetailWithWarranty = decimal(snapshot.pricing.retailWithWarranty);
  }
  if (snapshot.pricing.retailAsIs != null) data.priceRetailAsIs = decimal(snapshot.pricing.retailAsIs);
  if (snapshot.pricing.ownerAsking != null) data.priceOwnerAsking = decimal(snapshot.pricing.ownerAsking);
  if (snapshot.commercialHistory.normalized != null) {
    data.commercialHistory = snapshot.commercialHistory.normalized;
  }
  if (snapshot.commercialHistory.raw != null) {
    data.commercialHistoryRaw = snapshot.commercialHistory.raw;
  }
  if (!current.description) data.description = snapshot.rawDescription;

  await prisma.vehicle.update({ where: { id: row.vehicleId }, data });

  if (snapshot.stockType === "OWNED" && snapshot.ownership.owners.length > 0) {
    const partnerIds = await resolvePartnerIds(snapshot.ownership.owners);
    await prisma.vehicleOwner.deleteMany({ where: { vehicleId: row.vehicleId } });
    if (partnerIds.length) {
      await prisma.vehicleOwner.createMany({
        data: partnerIds.map((partnerId) => ({ vehicleId: row.vehicleId!, partnerId })),
      });
    }
  }
  return row.vehicleId;
}

export async function persistImportRun(opts: {
  sourceFile: string;
  schemaVersion?: string;
  dryRun: boolean;
  applied: boolean;
  plan: ReconcilePlan;
  appliedIds?: Map<string, string>;
}) {
  const summary = summarizePlan(opts.plan);
  const run = await prisma.vehicleInventoryImportRun.create({
    data: {
      sourceFile: opts.sourceFile,
      schemaVersion: opts.schemaVersion,
      dryRun: opts.dryRun,
      applied: opts.applied,
      summary: summary as Prisma.InputJsonValue,
      items: {
        create: opts.plan.rows.map((row) => ({
          spreadsheetKey: row.spreadsheetKey || `absent:${row.vehicleId ?? "unknown"}`,
          plateNormalized: row.plateNormalized,
          action: row.action,
          confidence: row.confidence,
          vehicleId: opts.appliedIds?.get(row.spreadsheetKey) ?? row.vehicleId,
          notes: row.notes,
          payload: snapshotPayload(row) as Prisma.InputJsonValue,
        })),
      },
    },
  });
  return { runId: run.id, summary };
}

export async function applyReconcilePlan(plan: ReconcilePlan): Promise<{
  inserted: number;
  updated: number;
  drafted: number;
  skippedConflicts: number;
  appliedIds: Map<string, string>;
}> {
  const seenAt = new Date();
  const appliedIds = new Map<string, string>();
  let inserted = 0;
  let updated = 0;
  let drafted = 0;
  let skippedConflicts = 0;

  for (const row of plan.rows) {
    if (row.action === "CONFLICT") {
      skippedConflicts += 1;
      continue;
    }
    if (row.action === "CREATE") {
      const id = await applyCreate(row, seenAt);
      appliedIds.set(row.spreadsheetKey, id);
      inserted += 1;
      continue;
    }
    if (row.action === "UPDATE") {
      const id = await applyUpdate(row, seenAt);
      appliedIds.set(row.spreadsheetKey, id);
      updated += 1;
      continue;
    }
    if (row.action === "DRAFT_ABSENT" && row.vehicleId) {
      await prisma.vehicle.update({
        where: { id: row.vehicleId },
        data: { status: "DRAFT", publishedAt: null },
      });
      drafted += 1;
    }
  }

  return { inserted, updated, drafted, skippedConflicts, appliedIds };
}

export function buildPlan(
  snapshots: SnapshotVehicle[],
  dbVehicles: DbVehicleForReconcile[],
  options?: ReconcileOptions,
): ReconcilePlan {
  return reconcileInventorySnapshot(snapshots, dbVehicles, options);
}
