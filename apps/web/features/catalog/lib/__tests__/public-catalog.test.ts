import { describe, expect, it } from "vitest";
import { buildPublicCatalogWhere, parseBodyStyleParam } from "../public-catalog";

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
