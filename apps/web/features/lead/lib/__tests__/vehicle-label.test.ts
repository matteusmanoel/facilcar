import { describe, expect, it } from "vitest";
import { leadVehicleLabel } from "../vehicle-label";
import { isDebugJuliaSummary, vendorSummaryFromLead } from "../julia-summary";

describe("leadVehicleLabel", () => {
  it("prefers the linked published vehicle title", () => {
    expect(
      leadVehicleLabel({
        vehicle: { title: "Toyota Corolla XEi" },
        metadataJson: { facts: { desired_model: "corolla" } },
      }),
    ).toBe("Toyota Corolla XEi");
  });

  it("falls back to interest text from facts, not a fake vehicle id", () => {
    expect(
      leadVehicleLabel({
        vehicle: null,
        vehicleInterests: [],
        metadataJson: { facts: { desired_model: "corolla" } },
      }),
    ).toBe("corolla");
  });
});

describe("vendorSummaryFromLead", () => {
  it("replaces Intent/Facts dump with a human brief", () => {
    const dump =
      'Intent: purchase | Business: PURCHASE | Actionability: INSUFFICIENT | Facts: {"desired_model": "corolla"}';
    expect(isDebugJuliaSummary(dump)).toBe(true);
    expect(
      vendorSummaryFromLead({
        name: "WhatsApp 0845",
        juliaSummary: dump,
        metadataJson: { intent: "purchase", facts: { desired_model: "corolla" } },
      }),
    ).toBe("Interesse: corolla · Forma: Compra");
  });
});


describe("leadVehicleLabel", () => {
  it("prefers the linked published vehicle title", () => {
    expect(
      leadVehicleLabel({
        vehicle: { title: "Toyota Corolla XEi" },
        metadataJson: { facts: { desired_model: "corolla" } },
      }),
    ).toBe("Toyota Corolla XEi");
  });

  it("falls back to interest text from facts, not a fake vehicle id", () => {
    expect(
      leadVehicleLabel({
        vehicle: null,
        vehicleInterests: [],
        metadataJson: { facts: { desired_model: "corolla" } },
      }),
    ).toBe("corolla");
  });
});
