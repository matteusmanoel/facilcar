import { describe, expect, it } from "vitest";
import { announcedPriceFromSnapshot } from "../announced-price";
import { displayColorFromSnapshot } from "../color";
import {
  canonicalBrand,
  modelsCompatible,
  reconcileInventorySnapshot,
  spreadsheetKey,
  type DbVehicleForReconcile,
  type SnapshotVehicle,
} from "../inventory-reconcile";
import { formatPlate, normalizePlate, plateFinalFromPlate } from "../plate";

function snapshot(overrides: Partial<SnapshotVehicle> & { vehicle?: Partial<SnapshotVehicle["vehicle"]> }): SnapshotVehicle {
  return {
    source: { sheet: "CARRO CONSIGNADO", row: 4 },
    stockType: "CONSIGNED",
    rawDescription: "FOCUS SEDAN 2.0 MANUAL",
    vehicle: {
      brand: "FORD",
      model: "Focus Sedan",
      version: "2.0",
      engineDisplacementLiters: 2,
      transmission: "MANUAL",
      year: 2011,
      color: "SILVER",
      plate: "ATI-1B43",
      mileageKm: 180000,
      ...overrides.vehicle,
    },
    commercialHistory: { raw: "LIMPO", normalized: "CLEAN" },
    pricing: { fipe: 36309, retailWithWarranty: 39900, retailAsIs: 33900, ownerAsking: null },
    ownership: { owners: [] },
    ...overrides,
  };
}

function db(overrides: Partial<DbVehicleForReconcile> = {}): DbVehicleForReconcile {
  return {
    id: "db-1",
    status: "PUBLISHED",
    title: "FORD FOCUS SEDAN",
    brandName: "Ford",
    brandId: "brand-ford",
    model: "FOCUS",
    version: null,
    yearManufacture: 2011,
    yearModel: 2011,
    mileage: 180000,
    color: null,
    plate: null,
    plateFinal: null,
    transmission: "MANUAL",
    engineDisplacementLiters: null,
    priceCash: 39900,
    description: "Anúncio WhatsApp",
    spreadsheetKey: null,
    stockType: null,
    ...overrides,
  };
}

describe("plate", () => {
  it("normalizes mercosul and old plates", () => {
    expect(normalizePlate("qiv-0g93")).toBe("QIV0G93");
    expect(normalizePlate("DZD-5956")).toBe("DZD5956");
    expect(formatPlate("QIV0G93")).toBe("QIV-0G93");
    expect(plateFinalFromPlate("ATI1B43")).toBe("3");
  });

  it("rejects invalid plates instead of matching", () => {
    expect(normalizePlate("ABC")).toBeNull();
    expect(normalizePlate("")).toBeNull();
  });
});

describe("announced price", () => {
  it("uses warranty price for consigned and cash for owned", () => {
    expect(
      announcedPriceFromSnapshot("CONSIGNED", { retailWithWarranty: 42900, retailAsIs: 31900, ownerAsking: 27900 }),
    ).toBe(42900);
    expect(announcedPriceFromSnapshot("OWNED", { cashPrice: 73900, fipe: 69421 })).toBe(73900);
    expect(announcedPriceFromSnapshot("OWNED", { cashPrice: null })).toBeNull();
  });
});

describe("identity helpers", () => {
  it("aliases chevrolet/gm and citroën", () => {
    expect(canonicalBrand("GM")).toBe(canonicalBrand("CHEVROLET"));
    expect(canonicalBrand("CITROËN")).toBe(canonicalBrand("Citroen"));
  });

  it("matches model tokens without brand lists", () => {
    expect(modelsCompatible("Focus Sedan", "FOCUS")).toBe(true);
    expect(modelsCompatible("Corsa Sedan", "CORSA")).toBe(true);
    expect(modelsCompatible("C4 Lounge", "C4 Pallas")).toBe(false);
  });

  it("maps snapshot colors to Portuguese labels", () => {
    expect(displayColorFromSnapshot("WHITE")).toBe("Branco");
    expect(displayColorFromSnapshot(null)).toBeNull();
  });
});

describe("reconcileInventorySnapshot", () => {
  it("matches unique brand+model+year when plate is missing in the database", () => {
    const plan = reconcileInventorySnapshot([snapshot({})], [db()]);
    expect(plan.rows[0]?.action).toBe("UPDATE");
    expect(plan.rows[0]?.confidence).toBe("HIGH");
    expect(plan.rows[0]?.vehicleId).toBe("db-1");
  });

  it("matches by plate on rerun", () => {
    const plan = reconcileInventorySnapshot(
      [snapshot({})],
      [db({ plate: "ATI1B43", model: "Outro" })],
    );
    expect(plan.rows[0]?.action).toBe("UPDATE");
    expect(plan.rows[0]?.notes).toMatch(/placa/i);
  });

  it("does not merge ambiguous identity and protects candidates from draft", () => {
    const plan = reconcileInventorySnapshot(
      [
        snapshot({
          source: { sheet: "Plan2", row: 18 },
          stockType: "OWNED",
          rawDescription: "RANGER XLT",
          vehicle: {
            brand: "FORD",
            model: "Ranger",
            version: "XLT",
            engineDisplacementLiters: null,
            transmission: null,
            year: null,
            color: "SILVER",
            plate: "CWZ-6G03",
            mileageKm: null,
          },
          pricing: { cashPrice: 32900 },
        }),
      ],
      [
        db({ id: "r1", brandName: "Ford", model: "RANGER", yearModel: 2000, yearManufacture: 2000, priceCash: 32900, plate: null }),
        db({ id: "r2", brandName: "Ford", model: "RANGER", yearModel: 2015, yearManufacture: 2015, priceCash: 99900 }),
      ],
    );
    const conflict = plan.rows.find((row) => row.action === "CONFLICT");
    expect(conflict).toBeTruthy();
    expect(plan.rows.some((row) => row.action === "DRAFT_ABSENT" && row.vehicleId === "r1")).toBe(false);
  });

  it("applies a confirmed match and keeps sibling rangers published", () => {
    const plan = reconcileInventorySnapshot(
      [
        snapshot({
          source: { sheet: "Plan2", row: 18 },
          stockType: "OWNED",
          rawDescription: "RANGER XLT",
          vehicle: {
            brand: "FORD",
            model: "Ranger",
            version: "XLT",
            engineDisplacementLiters: null,
            transmission: null,
            year: null,
            color: "SILVER",
            plate: "CWZ-6G03",
            mileageKm: null,
          },
          pricing: { cashPrice: 32900 },
          ownership: { owners: ["MILTON"] },
        }),
      ],
      [
        db({ id: "r2000", brandName: "Ford", model: "RANGER", yearModel: 2000, yearManufacture: 2000, priceCash: 32900 }),
        db({ id: "r2015xl", brandName: "Ford", model: "RANGER", yearModel: 2015, yearManufacture: 2015, priceCash: 99900 }),
        db({ id: "r2015xlt", brandName: "Ford", model: "RANGER", yearModel: 2015, yearManufacture: 2015, priceCash: 115900 }),
      ],
      { confirmedMatches: { "Plan2:18": "r2000" } },
    );
    expect(plan.rows.find((row) => row.spreadsheetKey === "Plan2:18")).toMatchObject({
      action: "UPDATE",
      vehicleId: "r2000",
    });
    expect(plan.rows.some((row) => row.action === "DRAFT_ABSENT")).toBe(false);
    expect(plan.protectedIds.has("r2015xl")).toBe(true);
    expect(plan.protectedIds.has("r2015xlt")).toBe(true);
  });

  it("creates when there is no candidate", () => {
    const plan = reconcileInventorySnapshot(
      [
        snapshot({
          source: { sheet: "CARRO CONSIGNADO", row: 8 },
          rawDescription: "LOGAN 1.6 COMPLETO",
          vehicle: {
            brand: "RENAULT",
            model: "Logan",
            version: "1.6 Completo",
            engineDisplacementLiters: 1.6,
            transmission: null,
            year: 2017,
            color: "WHITE",
            plate: "PYB-8C28",
            mileageKm: 135000,
          },
        }),
      ],
      [db()],
    );
    const created = plan.rows.find((row) => row.action === "CREATE");
    expect(created?.spreadsheetKey).toBe(spreadsheetKey("CARRO CONSIGNADO", 8));
  });

  it("drafts published vehicles absent from the snapshot", () => {
    const plan = reconcileInventorySnapshot([snapshot({})], [db(), db({ id: "pulse", model: "PULSE", yearModel: 2024, yearManufacture: 2024 })]);
    const drafted = plan.rows.filter((row) => row.action === "DRAFT_ABSENT");
    expect(drafted.map((row) => row.vehicleId)).toEqual(["pulse"]);
  });

  it("preserves existing values when the snapshot is null", () => {
    const plan = reconcileInventorySnapshot(
      [
        snapshot({
          vehicle: {
            brand: "FORD",
            model: "Focus Sedan",
            version: "2.0",
            engineDisplacementLiters: 2,
            transmission: null,
            year: 2011,
            color: "SILVER",
            plate: "ATI-1B43",
            mileageKm: null,
          },
          pricing: { retailWithWarranty: 39900, ownerAsking: null },
        }),
      ],
      [db({ mileage: 180000, transmission: "MANUAL" })],
    );
    const preserved = plan.rows[0]?.patches.filter((p) => p.preservedBecauseNull);
    expect(preserved?.some((p) => p.field === "mileage" && p.from === 180000)).toBe(true);
    expect(preserved?.some((p) => p.field === "transmission" && p.from === "MANUAL")).toBe(true);
  });

  it("spreadsheet announced price wins on conflict", () => {
    const plan = reconcileInventorySnapshot(
      [
        snapshot({
          source: { sheet: "Plan2", row: 4 },
          stockType: "OWNED",
          rawDescription: "AUDI Q5",
          vehicle: {
            brand: "AUDI",
            model: "Q5",
            version: null,
            engineDisplacementLiters: null,
            transmission: null,
            year: 2012,
            color: "WHITE",
            plate: "AFT-9D93",
            mileageKm: 190000,
          },
          pricing: { cashPrice: 73900, fipe: 69421 },
        }),
      ],
      [db({ id: "q5", brandName: "Audi", model: "Q5", yearModel: 2012, yearManufacture: 2012, priceCash: 74900, mileage: null })],
    );
    const price = plan.rows[0]?.patches.find((p) => p.field === "priceCash");
    expect(price).toEqual({ field: "priceCash", from: 74900, to: 73900 });
  });
});
