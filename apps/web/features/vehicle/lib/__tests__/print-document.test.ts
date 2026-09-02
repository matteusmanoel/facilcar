import { describe, expect, it } from "vitest";
import {
  customerListingUrl,
  toCustomerSheetModel,
  toStockListRow,
  truncateFeatureLabels,
  type CustomerSheetVehicleInput,
  type StockListVehicleInput,
} from "../print-document";

function stockVehicle(overrides: Partial<StockListVehicleInput> = {}): StockListVehicleInput {
  return {
    id: "v1",
    title: "Honda Civic EXL 2022",
    status: "PUBLISHED",
    type: "CAR",
    model: "Civic",
    version: "EXL",
    yearManufacture: 2021,
    yearModel: 2022,
    mileage: 42000,
    fuelType: "FLEX",
    transmission: "AUTOMATIC",
    engineDisplacementLiters: 2,
    color: "Preto",
    doors: 4,
    plateFinal: "7",
    priceCash: 98900,
    pricePromotional: 94900,
    priceTradeIn: 92000,
    aceitaTroca: true,
    aceitaSemEntrada: true,
    featured: false,
    parcelaBase: 1890,
    entradaMinima: 15000,
    rendaMinimaSugerida: 4500,
    prioridade: 2,
    city: "Cuiabá",
    state: "MT",
    brand: { name: "Honda" },
    ...overrides,
  };
}

function sheetVehicle(
  overrides: Partial<CustomerSheetVehicleInput> = {},
): CustomerSheetVehicleInput {
  return {
    status: "PUBLISHED",
    slug: "honda-civic-exl-2022",
    title: "Honda Civic EXL 2022",
    shortDescription: "Sedã automático com baixa km.",
    model: "Civic",
    version: "EXL",
    yearManufacture: 2021,
    yearModel: 2022,
    mileage: 42000,
    fuelType: "FLEX",
    transmission: "AUTOMATIC",
    engineDisplacementLiters: 2,
    color: "Preto",
    doors: 4,
    plateFinal: "7",
    priceCash: 98900,
    pricePromotional: 94900,
    priceTradeIn: 92000,
    aceitaTroca: true,
    aceitaSemEntrada: false,
    city: "Cuiabá",
    state: "MT",
    brand: { name: "Honda" },
    images: [
      { url: "https://cdn.example/cover.jpg", sortOrder: 0 },
      { url: "https://cdn.example/2.jpg", sortOrder: 1 },
    ],
    features: [
      { label: "Ar-condicionado", sortOrder: 0 },
      { label: "Couro", sortOrder: 1 },
    ],
    ...overrides,
  };
}

describe("toStockListRow", () => {
  it("includes the three prices and internal financing fields", () => {
    const row = toStockListRow(stockVehicle());
    expect(row.identity).toBe("Honda Civic EXL");
    expect(row.priceCashLabel).toMatch(/98\.900/);
    expect(row.pricePromotionalLabel).toMatch(/94\.900/);
    expect(row.priceTradeInLabel).toMatch(/92\.000/);
    expect(row.parcelaBaseLabel).toMatch(/1\.890/);
    expect(row.entradaMinimaLabel).toMatch(/15\.000/);
    expect(row.rendaMinimaLabel).toMatch(/4\.500/);
    expect(row.aceitaTroca).toBe(true);
    expect(row.plateFinal).toBe("7");
    expect(row).not.toHaveProperty("description");
    expect(row).not.toHaveProperty("features");
    expect(row).not.toHaveProperty("images");
  });

  it("falls back to title when version is empty", () => {
    const row = toStockListRow(stockVehicle({ version: "  ", title: "Honda Civic 2022" }));
    expect(row.identity).toBe("Honda Civic 2022");
  });
});

describe("toCustomerSheetModel", () => {
  const site = { listingBaseUrl: "https://facilcar.com.br" };

  it("projects public listing fields with cash as primary price", () => {
    const sheet = toCustomerSheetModel(sheetVehicle(), site);
    expect(sheet).not.toBeNull();
    expect(sheet!.priceCashLabel).toMatch(/98\.900/);
    expect(sheet!.pricePromotionalLabel).toMatch(/94\.900/);
    expect(sheet!.priceTradeInLabel).toMatch(/92\.000/);
    expect(sheet!.listingUrl).toBe(
      "https://facilcar.com.br/estoque/honda-civic-exl-2022",
    );
    expect(sheet!.coverUrl).toBe("https://cdn.example/cover.jpg");
    expect(sheet!.thumbUrls).toEqual(["https://cdn.example/2.jpg"]);
    expect(sheet!.plateFinal).toBe("7");
    expect(sheet!.specs.map((s) => s.label)).toContain("Marca");
    expect(sheet).not.toHaveProperty("parcelaBase");
    expect(sheet).not.toHaveProperty("entradaMinima");
    expect(sheet).not.toHaveProperty("rendaMinimaSugerida");
    expect(sheet).not.toHaveProperty("status");
    expect(sheet).not.toHaveProperty("estimatedMonthly");
  });

  it("does not generate a sheet for unpublished vehicles", () => {
    expect(toCustomerSheetModel(sheetVehicle({ status: "DRAFT" }), site)).toBeNull();
    expect(toCustomerSheetModel(sheetVehicle({ status: "SOLD" }), site)).toBeNull();
  });

  it("omits missing secondary prices", () => {
    const sheet = toCustomerSheetModel(
      sheetVehicle({ pricePromotional: null, priceTradeIn: null }),
      site,
    );
    expect(sheet!.pricePromotionalLabel).toBeNull();
    expect(sheet!.priceTradeInLabel).toBeNull();
  });
});

describe("truncateFeatureLabels", () => {
  it("keeps all labels when under the limit", () => {
    expect(truncateFeatureLabels(["Ar", "Couro"], 12)).toEqual({
      visible: ["Ar", "Couro"],
      remaining: 0,
    });
  });

  it("caps at 12 and reports the remainder", () => {
    const labels = Array.from({ length: 15 }, (_, i) => `Item ${i + 1}`);
    const result = truncateFeatureLabels(labels);
    expect(result.visible).toHaveLength(12);
    expect(result.remaining).toBe(3);
    expect(result.visible[0]).toBe("Item 1");
  });
});

describe("customerListingUrl", () => {
  it("joins base url and slug without duplicating slashes", () => {
    expect(customerListingUrl("https://facilcar.com.br/", "civic-2022")).toBe(
      "https://facilcar.com.br/estoque/civic-2022",
    );
  });
});
