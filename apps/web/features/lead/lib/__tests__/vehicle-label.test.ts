import { describe, expect, it } from "vitest";
import { leadVehicleLabel, nextPrimaryVehicleId, selectExplicitPrimary } from "../vehicle-label";
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

  it("does not use the first interest as the label when none is primary", () => {
    expect(
      leadVehicleLabel({
        vehicle: null,
        vehicleInterests: [
          { isPrimary: false, vehicle: { title: "Strada 2021" } },
          { isPrimary: false, vehicle: { title: "Strada 2017" } },
        ],
        metadataJson: { facts: { desired_model: "Strada" } },
      }),
    ).toBe("Strada");
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

describe("selectExplicitPrimary", () => {
  it("uses the explicit primary even when it is not first", () => {
    expect(
      selectExplicitPrimary([
        { isPrimary: false, vehicle: { title: "Strada 2021" } },
        { isPrimary: true, vehicle: { title: "Strada 2018" } },
        { isPrimary: false, vehicle: { title: "Strada 2017" } },
      ])?.vehicle.title,
    ).toBe("Strada 2018");
  });

  it("does not fall back to the first row when none is primary", () => {
    expect(
      selectExplicitPrimary([
        { isPrimary: false, vehicle: { title: "Strada 2021" } },
        { isPrimary: false, vehicle: { title: "Strada 2017" } },
      ]),
    ).toBeNull();
  });
});

describe("nextPrimaryVehicleId", () => {
  it("keeps the current primary when it remains selected", () => {
    expect(nextPrimaryVehicleId(["b", "a", "c"], "a")).toBe("a");
  });

  it("does not invent the first id when the primary was removed", () => {
    expect(nextPrimaryVehicleId(["b", "c"], "a")).toBeNull();
  });
});
