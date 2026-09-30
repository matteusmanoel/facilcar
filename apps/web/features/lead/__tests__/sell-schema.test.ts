import { describe, expect, it } from "vitest";
import { sellVehicleFormSchema } from "@/schemas/lead";

describe("sellVehicleFormSchema", () => {
  it("accepts a valid sell lead with consignment mode", () => {
    const parsed = sellVehicleFormSchema.safeParse({
      name: "Maria Silva",
      phone: "(45) 98823-0845",
      saleMode: "CONSIGNMENT",
    });
    expect(parsed.success).toBe(true);
  });

  it("accepts direct purchase sale mode", () => {
    const parsed = sellVehicleFormSchema.safeParse({
      name: "João Souza",
      phone: "11987654321",
      saleMode: "DIRECT_PURCHASE",
    });
    expect(parsed.success).toBe(true);
  });

  it("accepts a relato (text) alongside the mode", () => {
    const parsed = sellVehicleFormSchema.safeParse({
      name: "Ana Costa",
      phone: "45988230845",
      saleMode: "CONSIGNMENT",
      relato: "Fiat Uno 2018, 60 mil km, bem conservado.",
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.relato).toBe("Fiat Uno 2018, 60 mil km, bem conservado.");
    }
  });

  it("accepts empty relato (optional)", () => {
    const parsed = sellVehicleFormSchema.safeParse({
      name: "Ana Costa",
      phone: "45988230845",
      saleMode: "DIRECT_PURCHASE",
      relato: "",
    });
    expect(parsed.success).toBe(true);
  });

  it("rejects when saleMode is missing", () => {
    const parsed = sellVehicleFormSchema.safeParse({
      name: "Carlos",
      phone: "45988230845",
    });
    expect(parsed.success).toBe(false);
  });

  it("does not have brand, model, yearModel or mileage fields in schema", () => {
    const parsed = sellVehicleFormSchema.safeParse({
      name: "Carlos",
      phone: "45988230845",
      saleMode: "CONSIGNMENT",
      brand: "Toyota",
      model: "Corolla",
      yearModel: 2020,
      mileage: 30000,
    });
    // Extra fields are stripped by default in Zod
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect("brand" in parsed.data).toBe(false);
      expect("model" in parsed.data).toBe(false);
    }
  });
});
