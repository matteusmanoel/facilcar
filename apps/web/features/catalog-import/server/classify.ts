import { createHash } from "node:crypto";
import type { CatalogTextKind, FuelType, Transmission } from "@prisma/client";
import { parseEngineDisplacementFromAdText } from "@/features/vehicle/lib/engine-displacement";
import { isSuspiciousVehicleModel } from "@/features/vehicle/lib/suspicious-model";

const BRANDS = [
  "chevrolet",
  "volkswagen",
  "vw",
  "toyota",
  "honda",
  "fiat",
  "ford",
  "jeep",
  "nissan",
  "hyundai",
  "renault",
  "bmw",
  "mercedes",
  "audi",
  "peugeot",
  "citroen",
  "kia",
  "mitsubishi",
  "volvo",
  "byd",
  "cao",
  "ram",
  "chery",
];

function hasSignificantText(text: string | null | undefined): boolean {
  return !!text && text.trim().length >= 3;
}

function looksLikeContinuation(text: string): boolean {
  const t = text.trim().toLowerCase();
  if (/^r\$\s*[\d.,]+/.test(t)) return true;
  if (/^\d{1,3}(?:[.\s]\d{3})*\s*km\b/.test(t)) return true;
  if (/^(autom[aá]tico|manual|cvt|flex|diesel|gasolina|etanol|h[ií]brido|el[eé]trico)\b/.test(t))
    return true;
  if (/^(único dono|unico dono|aceita troca|completo|revisado|ipva pago)\b/.test(t)) return true;
  if (t.length <= 40 && !looksLikeVehicleHeadline(text)) return true;
  return false;
}

function looksLikeVehicleHeadline(text: string): boolean {
  const t = text.trim().toLowerCase();
  const hasBrand = BRANDS.some((b) => new RegExp(`\\b${b}\\b`, "i").test(t));
  const hasYear = /\b(19|20)\d{2}\b/.test(t);
  const hasPrice = /r\$\s*[\d.,]+/i.test(t);
  const lines = t.split(/\n/).filter(Boolean);
  if (hasBrand && (hasYear || hasPrice || lines.length >= 2)) return true;
  if (hasBrand && t.length >= 12) return true;
  return false;
}

function hasStructuredProduct(rawPayload: unknown): boolean {
  const s = JSON.stringify(rawPayload ?? {});
  return /productMessage|productSnapshot|"product"\s*:/i.test(s);
}

export function classifyEvent(input: {
  text: string | null;
  hasMedia: boolean;
  rawPayload: unknown;
}): CatalogTextKind {
  const significant = hasSignificantText(input.text);
  if (input.hasMedia && !significant) return "MEDIA_ONLY";
  if (hasStructuredProduct(input.rawPayload)) return "VEHICLE_START";
  if (significant && looksLikeVehicleHeadline(input.text!)) return "VEHICLE_START";
  if (significant && looksLikeContinuation(input.text!)) return "CONTINUATION";
  if (significant) return "CONTINUATION";
  return "UNKNOWN";
}

export type VehicleImportInput = {
  title: string | null;
  brand: string | null;
  model: string | null;
  version: string | null;
  yearManufacture: number | null;
  yearModel: number | null;
  mileage: number | null;
  fuel: FuelType | null;
  transmission: Transmission | null;
  engineDisplacementLiters: number | null;
  color: string | null;
  priceCash: string | null;
  shortDescription: string | null;
  description: string | null;
  features: string[];
  missingFields: string[];
  warnings: string[];
  source: "structured" | "openai" | "hybrid";
};

function parsePrice(text: string): string | null {
  const m = text.match(/r\$\s*([\d.]+(?:,\d{2})?)/i);
  if (!m?.[1]) return null;
  const normalized = m[1].replace(/\./g, "").replace(",", ".");
  const n = Number(normalized);
  if (!Number.isFinite(n)) return null;
  return n.toFixed(2);
}

function parseMileage(text: string): number | null {
  const m = text.match(/(\d{1,3}(?:[.\s]\d{3})*|\d+)\s*km\b/i);
  if (!m?.[1]) return null;
  const n = Number(m[1].replace(/[.\s]/g, ""));
  return Number.isFinite(n) ? n : null;
}

function parseYears(text: string): { yearManufacture: number | null; yearModel: number | null } {
  const years = [...text.matchAll(/\b((?:19|20)\d{2})\b/g)].map((x) => Number(x[1]));
  if (!years.length) return { yearManufacture: null, yearModel: null };
  if (years.length === 1) return { yearManufacture: years[0]!, yearModel: years[0]! };
  return { yearManufacture: years[0]!, yearModel: years[1]! };
}

function detectBrand(text: string): string | null {
  const lower = text.toLowerCase();
  for (const b of BRANDS) {
    if (new RegExp(`\\b${b}\\b`, "i").test(lower)) {
      if (b === "vw") return "Volkswagen";
      return b.charAt(0).toUpperCase() + b.slice(1);
    }
  }
  return null;
}

export function deterministicParseFromText(rawText: string): VehicleImportInput {
  const text = rawText.trim();
  const brand = detectBrand(text);
  const years = parseYears(text);
  const priceCash = parsePrice(text);
  const mileage = parseMileage(text);
  const firstLine = text.split(/\n/).map((l) => l.trim()).find(Boolean) ?? null;
  const missingFields: string[] = [];
  const warnings: string[] = [];
  if (!brand) missingFields.push("brand");
  if (!priceCash) missingFields.push("priceCash");
  if (mileage == null) missingFields.push("mileage");
  if (years.yearModel == null) missingFields.push("yearModel");
  missingFields.push("fuel", "transmission", "color", "model", "version");

  let model: string | null = null;
  if (brand && firstLine) {
    const after = firstLine.replace(new RegExp(brand, "i"), "").trim();
    const token = after.split(/\s+/).filter(Boolean)[0];
    model = token && !/^\d{4}$/.test(token) ? token : null;
    if (model && isSuspiciousVehicleModel(model)) {
      warnings.push("suspicious_model_token");
      model = null;
    }
    if (model) missingFields.splice(missingFields.indexOf("model"), 1);
  }

  const engineParse = parseEngineDisplacementFromAdText(text);
  if (engineParse.warning) warnings.push(engineParse.warning);
  if (engineParse.liters == null) missingFields.push("engineDisplacementLiters");

  return {
    title: firstLine,
    brand,
    model,
    version: null,
    yearManufacture: years.yearManufacture,
    yearModel: years.yearModel,
    mileage,
    fuel: null,
    transmission: null,
    engineDisplacementLiters: engineParse.liters,
    color: null,
    priceCash,
    shortDescription: firstLine,
    description: text,
    features: [],
    missingFields: [...new Set(missingFields)],
    warnings,
    source: "structured",
  };
}

export function computeVehicleFingerprint(input: {
  brand: string | null;
  model: string | null;
  version: string | null;
  yearModel: number | null;
  mileage: number | null;
  priceCash: string | null;
}): string {
  const norm = (v: string | number | null) =>
    String(v ?? "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]/g, "");
  const raw = [
    norm(input.brand),
    norm(input.model),
    norm(input.version),
    norm(input.yearModel),
    norm(input.mileage),
    norm(input.priceCash),
  ].join("|");
  return createHash("sha256").update(raw).digest("hex");
}
