import { describe, expect, it } from "vitest";
import {
  isInvalidNumber,
  maskCPF,
  parseDateInputValue,
  parseOptionalInt,
  parseOptionalNumber,
  toDateInputValue,
} from "../edit-values";
import {
  updateLeadContactSchema,
  updateLeadFinancingSchema,
  updateLeadSellSchema,
} from "@/schemas/lead";

describe("parseOptionalNumber", () => {
  it("treats blank as unset, not zero", () => {
    expect(parseOptionalNumber("")).toBeNull();
    expect(parseOptionalNumber("   ")).toBeNull();
    expect(parseOptionalNumber(undefined)).toBeNull();
  });

  it("parses money-like values", () => {
    expect(parseOptionalNumber("4500")).toBe(4500);
    expect(parseOptionalNumber("4500,50")).toBe(4500.5);
  });

  it("flags garbage as NaN", () => {
    expect(Number.isNaN(parseOptionalNumber("abc") as number)).toBe(true);
    expect(isInvalidNumber(parseOptionalNumber("abc"))).toBe(true);
  });
});

describe("parseOptionalInt", () => {
  it("accepts installment bounds", () => {
    expect(parseOptionalInt("36", { min: 1, max: 84 })).toBe(36);
    expect(isInvalidNumber(parseOptionalInt("0", { min: 1, max: 84 }))).toBe(true);
    expect(isInvalidNumber(parseOptionalInt("90", { min: 1, max: 84 }))).toBe(true);
  });
});

describe("date input helpers", () => {
  it("round-trips a calendar date without UTC shift", () => {
    const parsed = parseDateInputValue("1990-05-20");
    expect(parsed).toBeInstanceOf(Date);
    expect(toDateInputValue(parsed)).toBe("1990-05-20");
  });

  it("rejects malformed dates", () => {
    expect(parseDateInputValue("20/05/1990")).toBeNull();
    expect(parseDateInputValue("")).toBeNull();
  });
});

describe("maskCPF", () => {
  it("masks an 11-digit CPF and leaves incomplete values visible", () => {
    expect(maskCPF("123.456.789-00")).toBe("***.456.789-00");
    expect(maskCPF(null)).toBe("—");
    expect(maskCPF("123")).toBe("123");
  });
});

describe("updateLeadContactSchema", () => {
  const base = {
    leadId: "lead_1",
    name: "Ana Souza",
    phone: "(45) 99999-0000",
  };

  it("accepts contact edits and ignores untouched CPF", () => {
    const parsed = updateLeadContactSchema.safeParse({
      ...base,
      email: "ana@example.com",
      city: "Cascavel",
      state: "PR",
    });
    expect(parsed.success).toBe(true);
  });

  it("rejects a short name", () => {
    const parsed = updateLeadContactSchema.safeParse({ ...base, name: "A" });
    expect(parsed.success).toBe(false);
  });
});

describe("updateLeadFinancingSchema", () => {
  it("keeps money fields as strings so blank does not become 0", () => {
    const parsed = updateLeadFinancingSchema.safeParse({
      leadId: "lead_1",
      monthlyIncome: "",
      downPayment: "15000",
      desiredInstallments: "48",
      hasDriverLicense: "true",
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.monthlyIncome).toBe("");
      expect(parseOptionalNumber(parsed.data.monthlyIncome)).toBeNull();
      expect(parseOptionalNumber(parsed.data.downPayment)).toBe(15000);
    }
  });
});

describe("updateLeadSellSchema", () => {
  it("accepts clearing sale mode", () => {
    const parsed = updateLeadSellSchema.safeParse({
      leadId: "lead_1",
      brand: "Ford",
      saleMode: "",
    });
    expect(parsed.success).toBe(true);
  });
});
