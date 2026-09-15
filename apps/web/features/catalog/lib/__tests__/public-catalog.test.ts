import { describe, expect, it } from "vitest";
import { buildPublicCatalogWhere, parseBodyStyleParam, toPublicVehicleCard } from "../public-catalog";

describe("public catalog filters", () => {
  it("parses body style query values", () => {
    expect(parseBodyStyleParam("SUV")).toBe("SUV");
    expect(parseBodyStyleParam("sedan")).toBeUndefined();
    expect(parseBodyStyleParam(undefined)).toBeUndefined();
  });

  it("ANDs body style with type", () => {
    const where = buildPublicCatalogWhere({
      type: "MOTORCYCLE",
      bodyStyle: "SUV",
    });
    expect(where.status).toBe("PUBLISHED");
    expect(where.type).toBe("MOTORCYCLE");
    expect(where.bodyStyle).toBe("SUV");
  });
});

describe("toPublicVehicleCard", () => {
  it("serializes cash and repasse prices as numbers for client cards", () => {
    const card = toPublicVehicleCard({
      id: "1",
      slug: "civic",
      title: "Civic",
      model: "Civic",
      version: "EXL",
      priceCash: { valueOf: () => 74900 },
      priceRetailAsIs: "69900.00",
      yearManufacture: 2020,
      yearModel: 2021,
      mileage: 30000,
      fuelType: "FLEX",
      transmission: "AUTOMATIC",
      bodyStyle: "SEDAN",
      inspectionResult: "APPROVED",
      brand: { name: "Honda", logoUrl: null },
      images: [{ url: "/civic.jpg" }],
    });

    expect(card.priceCash).toBe(74900);
    expect(card.priceRetailAsIs).toBe(69900);
  });
});
