import { describe, expect, it } from "vitest";
import { sellVehicleFormSchema } from "@/schemas/lead";

describe("sellVehicleFormSchema", () => {
  it("accepts a sell lead without email", () => {
    const parsed = sellVehicleFormSchema.safeParse({
      name: "Maria Silva",
      phone: "(45) 98823-0845",
      brand: "Toyota",
      model: "Corolla",
      yearModel: 2020,
      saleMode: "CONSIGNMENT",
    });
    expect(parsed.success).toBe(true);
  });

  it("strips unknown email keys from public sell form", () => {
    const parsed = sellVehicleFormSchema.safeParse({
      name: "Maria Silva",
      phone: "45988230845",
      email: "maria@example.com",
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect("email" in parsed.data).toBe(false);
    }
  });

  it("accepts direct purchase sale mode", () => {
    const parsed = sellVehicleFormSchema.safeParse({
      name: "João Souza",
      phone: "11987654321",
      saleMode: "DIRECT_PURCHASE",
    });
    expect(parsed.success).toBe(true);
  });
});
