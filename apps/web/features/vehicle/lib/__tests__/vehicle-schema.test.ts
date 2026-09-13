import { describe, expect, it } from "vitest";
import { createVehicleSchema } from "@/schemas/vehicle";
import { bodyStyleLabels, inspectionResultLabels } from "@/features/vehicle/lib/labels";

const base = {
  status: "DRAFT" as const,
  type: "CAR" as const,
  title: "Toyota Corolla XEi",
  brandId: "brand-1",
  model: "Corolla",
};

describe("createVehicleSchema bodyStyle", () => {
  it("accepts sedan on a car", () => {
    const parsed = createVehicleSchema.safeParse({ ...base, bodyStyle: "SEDAN" });
    expect(parsed.success).toBe(true);
  });

  it("rejects body style on a motorcycle", () => {
    const parsed = createVehicleSchema.safeParse({
      ...base,
      type: "MOTORCYCLE",
      bodyStyle: "SUV",
    });
    expect(parsed.success).toBe(false);
    if (!parsed.success) {
      expect(parsed.error.issues.some((issue) => issue.path.includes("bodyStyle"))).toBe(true);
    }
  });

  it("accepts a motorcycle without body style", () => {
    const parsed = createVehicleSchema.safeParse({
      ...base,
      type: "MOTORCYCLE",
    });
    expect(parsed.success).toBe(true);
  });
});

describe("vehicle labels", () => {
  it("names body styles and inspection results", () => {
    expect(bodyStyleLabels.SEDAN).toBe("Sedan");
    expect(bodyStyleLabels.HATCH).toBe("Hatch");
    expect(bodyStyleLabels.SUV).toBe("SUV");
    expect(inspectionResultLabels.APPROVED).toBe("Aprovado na perícia");
    expect(inspectionResultLabels.REJECTED).toBe("Reprovado na perícia");
  });
});
