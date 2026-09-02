import { describe, expect, it } from "vitest";
import {
  formatBRL,
  formatCNPJ,
  formatCPF,
  formatPhoneBR,
  parseBRL,
} from "@/lib/input-masks";

describe("formatPhoneBR", () => {
  it("masks a mobile number as the user types", () => {
    expect(formatPhoneBR("4")).toBe("(4");
    expect(formatPhoneBR("45")).toBe("(45");
    expect(formatPhoneBR("45988")).toBe("(45) 988");
    expect(formatPhoneBR("45988230845")).toBe("(45) 98823-0845");
  });

  it("strips non-digits and caps national numbers at 11", () => {
    expect(formatPhoneBR("(45) 98823-0845 extra")).toBe("(45) 98823-0845");
  });

  it("keeps country-coded WhatsApp numbers instead of truncating", () => {
    expect(formatPhoneBR("554588230845")).toBe("+55 (45) 8823-0845");
    expect(formatPhoneBR("5545988230845")).toBe("+55 (45) 98823-0845");
    expect(formatPhoneBR("+55 (45) 98823-0845 extra")).toBe("+55 (45) 98823-0845");
  });
});

describe("formatCPF", () => {
  it("masks an 11-digit CPF", () => {
    expect(formatCPF("12345678901")).toBe("123.456.789-01");
  });
});

describe("formatCNPJ", () => {
  it("masks a 14-digit CNPJ", () => {
    expect(formatCNPJ("12345678000195")).toBe("12.345.678/0001-95");
  });
});

describe("BRL mask", () => {
  it("formats cents as Brazilian currency", () => {
    expect(formatBRL(45000)).toBe("45.000,00");
    expect(formatBRL(undefined)).toBe("");
  });

  it("parses typed digits as cents", () => {
    expect(parseBRL("1")).toBe(0.01);
    expect(parseBRL("4500000")).toBe(45000);
    expect(parseBRL("45.000,00")).toBe(45000);
    expect(parseBRL("")).toBeUndefined();
  });
});
