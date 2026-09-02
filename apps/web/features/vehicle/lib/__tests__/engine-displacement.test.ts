import { describe, expect, it } from "vitest";
import {
  normalizeEngineDisplacementLiters,
  parseEngineDisplacementFromAdText,
} from "../engine-displacement";
import { isSuspiciousVehicleModel } from "../suspicious-model";

describe("engine displacement", () => {
  it("normalizes commercial liters", () => {
    expect(normalizeEngineDisplacementLiters("1.4")).toBe(1.4);
    expect(normalizeEngineDisplacementLiters("2,0")).toBe(2.0);
    expect(normalizeEngineDisplacementLiters(1.8)).toBe(1.8);
  });

  it("rejects compound labels", () => {
    expect(normalizeEngineDisplacementLiters("1.0 TSI")).toBeNull();
    expect(normalizeEngineDisplacementLiters("2.0 Turbo")).toBeNull();
    expect(normalizeEngineDisplacementLiters("1.4 Fire Flex")).toBeNull();
  });

  it("does not invent motor from ambiguous ad text", () => {
    const parsed = parseEngineDisplacementFromAdText(
      "FIAT STRADA WORKING 1.4 ou 1.8 Fire Flex Manual",
    );
    expect(parsed.liters).toBeNull();
    expect(parsed.warning).toBe("ENGINE_AMBIGUOUS");
  });

  it("splits a single numeric token and warns on qualifier", () => {
    const parsed = parseEngineDisplacementFromAdText("STRADA WORKING 1.4 Fire Flex");
    expect(parsed.liters).toBe(1.4);
    expect(parsed.warning).toBe("ENGINE_QUALIFIER_UNSPLIT");
  });
});

describe("suspicious model", () => {
  it("rejects View and Não informado", () => {
    expect(isSuspiciousVehicleModel("View")).toBe(true);
    expect(isSuspiciousVehicleModel("\u200eView")).toBe(true);
    expect(isSuspiciousVehicleModel("Não informado")).toBe(true);
    expect(isSuspiciousVehicleModel("Corolla")).toBe(false);
  });
});
