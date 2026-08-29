import { describe, expect, it } from "vitest";
import {
  applyPrintListDefaults,
  buildAdminVehicleWhere,
  parseAdminVehicleListParams,
} from "../admin-vehicle-filters";

describe("parseAdminVehicleListParams", () => {
  it("parses csv filters and pagination", () => {
    const parsed = parseAdminVehicleListParams({
      q: "civic",
      status: "PUBLISHED,DRAFT",
      brandId: "b1,b2",
      type: "CAR",
      featured: "true",
      hasPhoto: "false",
      fuelType: "FLEX",
      transmission: "AUTOMATIC",
      priceMin: "10000",
      priceMax: "80000",
      yearMin: "2018",
      yearMax: "2024",
      page: "2",
      pageSize: "50",
      ids: "a,b,c",
    });

    expect(parsed.search).toBe("civic");
    expect(parsed.statuses).toEqual(["PUBLISHED", "DRAFT"]);
    expect(parsed.brandIds).toEqual(["b1", "b2"]);
    expect(parsed.types).toEqual(["CAR"]);
    expect(parsed.featuredValues).toEqual([true]);
    expect(parsed.hasPhotoValues).toEqual([false]);
    expect(parsed.fuelTypes).toEqual(["FLEX"]);
    expect(parsed.transmissions).toEqual(["AUTOMATIC"]);
    expect(parsed.priceMin).toBe(10000);
    expect(parsed.priceMax).toBe(80000);
    expect(parsed.yearMin).toBe(2018);
    expect(parsed.yearMax).toBe(2024);
    expect(parsed.page).toBe(2);
    expect(parsed.pageSize).toBe(50);
    expect(parsed.ids).toEqual(["a", "b", "c"]);
  });

  it("ignores unknown enum tokens", () => {
    const parsed = parseAdminVehicleListParams({ status: "PUBLISHED,NOPE" });
    expect(parsed.statuses).toEqual(["PUBLISHED"]);
  });
});

describe("applyPrintListDefaults", () => {
  it("forces PUBLISHED when no status and no ids", () => {
    const next = applyPrintListDefaults({ search: "corolla" });
    expect(next.statuses).toEqual(["PUBLISHED"]);
    expect(next.search).toBe("corolla");
  });

  it("keeps explicit statuses", () => {
    const next = applyPrintListDefaults({ statuses: ["RESERVED", "SOLD"] });
    expect(next.statuses).toEqual(["RESERVED", "SOLD"]);
  });

  it("lets ids prevail and drops other filters", () => {
    const next = applyPrintListDefaults({
      ids: ["v1", "v2"],
      statuses: ["PUBLISHED"],
      search: "civic",
      brandIds: ["honda"],
    });
    expect(next).toEqual({ ids: ["v1", "v2"] });
  });
});

describe("buildAdminVehicleWhere", () => {
  it("uses only ids when present", () => {
    expect(buildAdminVehicleWhere({ ids: ["a", "b"], statuses: ["PUBLISHED"] })).toEqual({
      id: { in: ["a", "b"] },
    });
  });

  it("maps status, brand, search and price range", () => {
    const where = buildAdminVehicleWhere(
      applyPrintListDefaults({
        brandIds: ["brand-1"],
        priceMin: 20000,
        search: "Civic",
      }),
    );
    expect(where.status).toEqual({ in: ["PUBLISHED"] });
    expect(where.brandId).toEqual({ in: ["brand-1"] });
    expect(where.priceCash).toEqual({ gte: 20000 });
    expect(where.OR).toEqual(
      expect.arrayContaining([
        { title: { contains: "Civic", mode: "insensitive" } },
        { model: { contains: "Civic", mode: "insensitive" } },
        { plate: { contains: "Civic", mode: "insensitive" } },
      ]),
    );
  });

  it("maps stock type and commercial history", () => {
    const where = buildAdminVehicleWhere({
      stockTypes: ["CONSIGNED"],
      commercialHistories: ["AUCTION"],
    });
    expect(where.stockType).toEqual({ in: ["CONSIGNED"] });
    expect(where.commercialHistory).toEqual({ in: ["AUCTION"] });
  });

  it("filters vehicles with photos", () => {
    expect(buildAdminVehicleWhere({ hasPhotoValues: [true] }).images).toEqual({ some: {} });
  });

  it("filters vehicles without photos", () => {
    expect(buildAdminVehicleWhere({ hasPhotoValues: [false] }).images).toEqual({ none: {} });
  });

  it("does not filter photos when both options are selected", () => {
    expect(buildAdminVehicleWhere({ hasPhotoValues: [true, false] }).images).toBeUndefined();
  });
});
