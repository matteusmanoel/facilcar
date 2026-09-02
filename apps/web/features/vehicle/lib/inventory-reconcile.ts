import { normalizePlate, plateFinalFromPlate } from "./plate";
import { displayColorFromSnapshot } from "./color";
import { announcedPriceFromSnapshot, type SnapshotPricing, type VehicleStockTypeValue } from "./announced-price";

export type CommercialHistoryValue =
  | "CLEAN"
  | "AUCTION"
  | "RECOVERED_CLAIM"
  | "AUCTION_AND_RECOVERED_CLAIM";

export type SnapshotVehicle = {
  source: { sheet: string; row: number };
  stockType: VehicleStockTypeValue;
  rawDescription: string;
  vehicle: {
    brand: string;
    model: string;
    version: string | null;
    engineDisplacementLiters: number | null;
    transmission: "MANUAL" | "AUTOMATIC" | "AUTOMATED" | "CVT" | "OTHER" | null;
    year: number | null;
    color: string | null;
    plate: string | null;
    mileageKm: number | null;
  };
  commercialHistory: { raw: string | null; normalized: CommercialHistoryValue | null };
  pricing: SnapshotPricing;
  ownership: { owners: string[]; ownershipShares?: number[] | null };
};

export type DbVehicleForReconcile = {
  id: string;
  status: string;
  title: string;
  brandName: string;
  brandId: string;
  model: string;
  version: string | null;
  yearManufacture: number | null;
  yearModel: number | null;
  mileage: number | null;
  color: string | null;
  plate: string | null;
  plateFinal: string | null;
  transmission: string | null;
  engineDisplacementLiters: number | null;
  priceCash: number | null;
  description: string | null;
  spreadsheetKey: string | null;
  stockType: VehicleStockTypeValue | null;
};

export type ReconcileAction =
  | "UPDATE"
  | "CREATE"
  | "CONFLICT"
  | "DRAFT_ABSENT";

export type ReconcileConfidence = "HIGH" | "MEDIUM" | "NONE";

export type FieldPatch = {
  field: string;
  from: unknown;
  to: unknown;
  preservedBecauseNull?: boolean;
};

export type ReconcileRow = {
  action: ReconcileAction;
  confidence: ReconcileConfidence;
  spreadsheetKey: string;
  plateNormalized: string | null;
  snapshot: SnapshotVehicle;
  vehicleId: string | null;
  candidateIds: string[];
  notes: string;
  patches: FieldPatch[];
  ownerNames: string[];
};

export type ReconcilePlan = {
  rows: ReconcileRow[];
  protectedIds: Set<string>;
};

export type ReconcileOptions = {
  confirmedMatches?: Record<string, string>;
};

const BRAND_ALIASES: Record<string, string> = {
  chevrolet: "chevrolet",
  gm: "chevrolet",
  chevy: "chevrolet",
  volkswagen: "volkswagen",
  vw: "volkswagen",
  citroen: "citroen",
  "citroën": "citroen",
  citroëen: "citroen",
};

export function spreadsheetKey(sheet: string, row: number): string {
  return `${sheet.trim()}:${row}`;
}

export function normalizeToken(value: string | null | undefined): string {
  if (!value) return "";
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

export function canonicalBrand(name: string | null | undefined): string {
  const token = normalizeToken(name);
  return BRAND_ALIASES[token] ?? token;
}

export function modelsCompatible(a: string | null | undefined, b: string | null | undefined): boolean {
  const left = normalizeToken(a);
  const right = normalizeToken(b);
  if (!left || !right) return false;
  if (left === right) return true;
  const leftTokens = left.split(" ");
  const rightTokens = right.split(" ");
  const [shorter, longer] = leftTokens.length <= rightTokens.length ? [leftTokens, rightTokens] : [rightTokens, leftTokens];
  return shorter.every((token) => longer.includes(token));
}

export function dbYear(vehicle: Pick<DbVehicleForReconcile, "yearModel" | "yearManufacture">): number | null {
  return vehicle.yearModel ?? vehicle.yearManufacture ?? null;
}

function patchIfPresent(
  patches: FieldPatch[],
  field: string,
  from: unknown,
  to: unknown,
): void {
  if (to === null || to === undefined) {
    if (from !== null && from !== undefined && from !== "") {
      patches.push({ field, from, to: from, preservedBecauseNull: true });
    }
    return;
  }
  if (from === to) return;
  patches.push({ field, from, to });
}

export function buildFieldPatches(
  snapshot: SnapshotVehicle,
  current: DbVehicleForReconcile | null,
): FieldPatch[] {
  const patches: FieldPatch[] = [];
  const announced = announcedPriceFromSnapshot(snapshot.stockType, snapshot.pricing);
  const plate = normalizePlate(snapshot.vehicle.plate);
  const color = displayColorFromSnapshot(snapshot.vehicle.color);
  const year = snapshot.vehicle.year;

  patchIfPresent(patches, "stockType", current?.stockType ?? null, snapshot.stockType);
  patchIfPresent(patches, "model", current?.model ?? null, snapshot.vehicle.model);
  patchIfPresent(patches, "version", current?.version ?? null, snapshot.vehicle.version);
  patchIfPresent(patches, "yearManufacture", current?.yearManufacture ?? null, year);
  patchIfPresent(patches, "yearModel", current?.yearModel ?? null, year);
  patchIfPresent(patches, "mileage", current?.mileage ?? null, snapshot.vehicle.mileageKm);
  patchIfPresent(patches, "color", current?.color ?? null, color);
  patchIfPresent(patches, "plate", current?.plate ?? null, plate);
  patchIfPresent(patches, "plateFinal", current?.plateFinal ?? null, plateFinalFromPlate(plate));
  patchIfPresent(patches, "transmission", current?.transmission ?? null, snapshot.vehicle.transmission);
  patchIfPresent(
    patches,
    "engineDisplacementLiters",
    current?.engineDisplacementLiters ?? null,
    snapshot.vehicle.engineDisplacementLiters,
  );
  patchIfPresent(patches, "priceCash", current?.priceCash ?? null, announced);
  patchIfPresent(patches, "priceFipe", null, snapshot.pricing.fipe ?? null);
  patchIfPresent(patches, "priceRetailWithWarranty", null, snapshot.pricing.retailWithWarranty ?? null);
  patchIfPresent(patches, "priceRetailAsIs", null, snapshot.pricing.retailAsIs ?? null);
  patchIfPresent(patches, "priceOwnerAsking", null, snapshot.pricing.ownerAsking ?? null);
  patchIfPresent(patches, "commercialHistory", null, snapshot.commercialHistory.normalized);
  patchIfPresent(patches, "commercialHistoryRaw", null, snapshot.commercialHistory.raw);
  patchIfPresent(patches, "sourceRawDescription", null, snapshot.rawDescription);

  if (current?.description) {
    patches.push({
      field: "description",
      from: current.description,
      to: current.description,
      preservedBecauseNull: true,
    });
  } else {
    patchIfPresent(patches, "description", current?.description ?? null, snapshot.rawDescription);
  }

  return patches;
}

function identityCandidates(
  snapshot: SnapshotVehicle,
  dbVehicles: DbVehicleForReconcile[],
): DbVehicleForReconcile[] {
  const year = snapshot.vehicle.year;
  if (year == null) {
    return dbVehicles.filter(
      (row) =>
        canonicalBrand(row.brandName) === canonicalBrand(snapshot.vehicle.brand) &&
        modelsCompatible(row.model, snapshot.vehicle.model),
    );
  }
  return dbVehicles.filter(
    (row) =>
      canonicalBrand(row.brandName) === canonicalBrand(snapshot.vehicle.brand) &&
      modelsCompatible(row.model, snapshot.vehicle.model) &&
      dbYear(row) === year,
  );
}

function protectIdentitySiblings(
  snapshot: SnapshotVehicle,
  dbVehicles: DbVehicleForReconcile[],
  protectedIds: Set<string>,
) {
  for (const hit of identityCandidates(snapshot, dbVehicles)) {
    protectedIds.add(hit.id);
  }
}

export function reconcileInventorySnapshot(
  snapshots: SnapshotVehicle[],
  dbVehicles: DbVehicleForReconcile[],
  options: ReconcileOptions = {},
): ReconcilePlan {
  const byPlate = new Map<string, DbVehicleForReconcile[]>();
  const byKey = new Map<string, DbVehicleForReconcile>();
  for (const row of dbVehicles) {
    const plate = normalizePlate(row.plate);
    if (plate) {
      const list = byPlate.get(plate) ?? [];
      list.push(row);
      byPlate.set(plate, list);
    }
    if (row.spreadsheetKey) byKey.set(row.spreadsheetKey, row);
  }

  const usedIds = new Set<string>();
  const protectedIds = new Set<string>();
  const rows: ReconcileRow[] = [];

  for (const snapshot of snapshots) {
    const key = spreadsheetKey(snapshot.source.sheet, snapshot.source.row);
    const plate = normalizePlate(snapshot.vehicle.plate);
    let matched: DbVehicleForReconcile | null = null;
    let confidence: ReconcileConfidence = "NONE";
    let candidateIds: string[] = [];
    let notes = "";

    const confirmedId = options.confirmedMatches?.[key];
    if (confirmedId) {
      const target = dbVehicles.find((row) => row.id === confirmedId);
      if (!target) {
        rows.push({
          action: "CONFLICT",
          confidence: "NONE",
          spreadsheetKey: key,
          plateNormalized: plate,
          snapshot,
          vehicleId: null,
          candidateIds: [confirmedId],
          notes: "Correspondência confirmada aponta para um id inexistente.",
          patches: [],
          ownerNames: snapshot.ownership.owners,
        });
        continue;
      }
      matched = target;
      confidence = "HIGH";
      notes = "Correspondência confirmada manualmente.";
      candidateIds = identityCandidates(snapshot, dbVehicles).map((row) => row.id);
    }

    const keyHit = byKey.get(key);
    if (!matched && keyHit && !usedIds.has(keyHit.id)) {
      matched = keyHit;
      confidence = "HIGH";
      notes = "Correspondência pelo identificador da planilha (reexecução).";
    }

    if (!matched && plate) {
      const plateHits = (byPlate.get(plate) ?? []).filter((row) => !usedIds.has(row.id));
      candidateIds = plateHits.map((row) => row.id);
      if (plateHits.length === 1) {
        matched = plateHits[0]!;
        confidence = "HIGH";
        notes = "Correspondência por placa.";
      } else if (plateHits.length > 1) {
        rows.push({
          action: "CONFLICT",
          confidence: "NONE",
          spreadsheetKey: key,
          plateNormalized: plate,
          snapshot,
          vehicleId: null,
          candidateIds,
          notes: "Placa encontrada em mais de um registro. Merge automático recusado.",
          patches: [],
          ownerNames: snapshot.ownership.owners,
        });
        for (const hit of plateHits) protectedIds.add(hit.id);
        continue;
      }
    }

    if (!matched) {
      const identityHits = identityCandidates(snapshot, dbVehicles).filter((row) => !usedIds.has(row.id));
      candidateIds = identityHits.map((row) => row.id);
      if (snapshot.vehicle.year == null && identityHits.length !== 1) {
        if (identityHits.length === 0) {
          rows.push({
            action: "CREATE",
            confidence: "HIGH",
            spreadsheetKey: key,
            plateNormalized: plate,
            snapshot,
            vehicleId: null,
            candidateIds: [],
            notes: "Sem placa e sem ano; nenhum candidato no banco. Alta para inserção.",
            patches: buildFieldPatches(snapshot, null),
            ownerNames: snapshot.ownership.owners,
          });
          continue;
        }
        rows.push({
          action: "CONFLICT",
          confidence: "NONE",
          spreadsheetKey: key,
          plateNormalized: plate,
          snapshot,
          vehicleId: null,
          candidateIds,
          notes: "Ano ausente e mais de um candidato da mesma marca/modelo. Merge automático recusado.",
          patches: [],
          ownerNames: snapshot.ownership.owners,
        });
        for (const hit of identityHits) protectedIds.add(hit.id);
        continue;
      }
      if (identityHits.length === 1) {
        matched = identityHits[0]!;
        confidence = "HIGH";
        notes = "Correspondência única por marca, modelo e ano.";
      } else if (identityHits.length > 1) {
        rows.push({
          action: "CONFLICT",
          confidence: "NONE",
          spreadsheetKey: key,
          plateNormalized: plate,
          snapshot,
          vehicleId: null,
          candidateIds,
          notes: "Mais de um registro com a mesma identidade. Merge automático recusado.",
          patches: [],
          ownerNames: snapshot.ownership.owners,
        });
        for (const hit of identityHits) protectedIds.add(hit.id);
        continue;
      }
    }

    if (matched) {
      usedIds.add(matched.id);
      protectIdentitySiblings(snapshot, dbVehicles, protectedIds);
      rows.push({
        action: "UPDATE",
        confidence,
        spreadsheetKey: key,
        plateNormalized: plate,
        snapshot,
        vehicleId: matched.id,
        candidateIds: [matched.id],
        notes,
        patches: buildFieldPatches(snapshot, matched),
        ownerNames: snapshot.ownership.owners,
      });
      continue;
    }

    rows.push({
      action: "CREATE",
      confidence: "HIGH",
      spreadsheetKey: key,
      plateNormalized: plate,
      snapshot,
      vehicleId: null,
      candidateIds: [],
      notes: "Nenhum registro correspondente com confiança suficiente.",
      patches: buildFieldPatches(snapshot, null),
      ownerNames: snapshot.ownership.owners,
    });
  }

  for (const row of dbVehicles) {
    if (protectedIds.has(row.id)) continue;
    if (row.status !== "PUBLISHED") continue;
    rows.push({
      action: "DRAFT_ABSENT",
      confidence: "HIGH",
      spreadsheetKey: row.spreadsheetKey ?? `absent:${row.id}`,
      plateNormalized: normalizePlate(row.plate),
      snapshot: {
        source: { sheet: "", row: 0 },
        stockType: "OWNED",
        rawDescription: row.title,
        vehicle: {
          brand: row.brandName,
          model: row.model,
          version: row.version,
          engineDisplacementLiters: row.engineDisplacementLiters,
          transmission: null,
          year: dbYear(row),
          color: row.color,
          plate: row.plate,
          mileageKm: row.mileage,
        },
        commercialHistory: { raw: null, normalized: null },
        pricing: {},
        ownership: { owners: [] },
      },
      vehicleId: row.id,
      candidateIds: [row.id],
      notes: "Publicado no banco e ausente do snapshot. Status previsto: DRAFT.",
      patches: [{ field: "status", from: row.status, to: "DRAFT" }],
      ownerNames: [],
    });
  }

  return { rows, protectedIds };
}
