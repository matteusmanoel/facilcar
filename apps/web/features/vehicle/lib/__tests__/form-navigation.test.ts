import { describe, expect, it } from "vitest";
import { vehicleFormFooterAction } from "../form-navigation";

describe("vehicleFormFooterAction", () => {
  const stepCount = 4;

  it("keeps Precificação (step 2) as next, not save", () => {
    expect(vehicleFormFooterAction(2, stepCount)).toBe("next");
  });

  it("only the last step (Mídia & SEO) is save", () => {
    expect(vehicleFormFooterAction(3, stepCount)).toBe("save");
  });

  it("never treats an earlier step as save", () => {
    expect(vehicleFormFooterAction(0, stepCount)).toBe("next");
    expect(vehicleFormFooterAction(1, stepCount)).toBe("next");
  });
});
