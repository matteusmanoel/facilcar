import { describe, expect, it } from "vitest";
import { shouldShowInspectionSeal } from "../inspection-seal";

describe("shouldShowInspectionSeal", () => {
  it("shows the seal only when approved", () => {
    expect(shouldShowInspectionSeal("APPROVED")).toBe(true);
    expect(shouldShowInspectionSeal("REJECTED")).toBe(false);
    expect(shouldShowInspectionSeal(null)).toBe(false);
    expect(shouldShowInspectionSeal(undefined)).toBe(false);
  });
});
