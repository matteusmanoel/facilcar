import OpenAI from "openai";
import type { FuelType, Transmission } from "@prisma/client";
import type { VehicleImportInput } from "./classify";
import { normalizeEngineDisplacementLiters } from "@/features/vehicle/lib/engine-displacement";

const FUELS: FuelType[] = [
  "GASOLINE",
  "ETHANOL",
  "FLEX",
  "DIESEL",
  "ELECTRIC",
  "HYBRID",
  "OTHER",
];
const TRANSMISSIONS: Transmission[] = ["MANUAL", "AUTOMATIC", "AUTOMATED", "CVT", "OTHER"];

function asFuel(v: unknown): FuelType | null {
  return typeof v === "string" && (FUELS as string[]).includes(v) ? (v as FuelType) : null;
}
function asTransmission(v: unknown): Transmission | null {
  return typeof v === "string" && (TRANSMISSIONS as string[]).includes(v)
    ? (v as Transmission)
    : null;
}

export async function openaiExtractVehicle(rawText: string): Promise<VehicleImportInput> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is not set");
  }
  const client = new OpenAI({ apiKey });
  const response = await client.chat.completions.create({
    model: process.env.OPENAI_CATALOG_MODEL ?? "gpt-4o-mini",
    temperature: 0,
    response_format: {
      type: "json_schema",
      json_schema: {
        name: "vehicle_import_input",
        strict: true,
        schema: {
          type: "object",
          additionalProperties: false,
          properties: {
            title: { type: ["string", "null"] },
            brand: { type: ["string", "null"] },
            model: { type: ["string", "null"] },
            version: { type: ["string", "null"] },
            yearManufacture: { type: ["integer", "null"] },
            yearModel: { type: ["integer", "null"] },
            mileage: { type: ["integer", "null"] },
            fuel: {
              type: ["string", "null"],
              enum: [...FUELS, null],
            },
            transmission: {
              type: ["string", "null"],
              enum: [...TRANSMISSIONS, null],
            },
            engineDisplacementLiters: { type: ["number", "null"] },
            color: { type: ["string", "null"] },
            priceCash: { type: ["string", "null"] },
            shortDescription: { type: ["string", "null"] },
            description: { type: ["string", "null"] },
            features: { type: "array", items: { type: "string" } },
            missingFields: { type: "array", items: { type: "string" } },
            warnings: { type: "array", items: { type: "string" } },
          },
          required: [
            "title",
            "brand",
            "model",
            "version",
            "yearManufacture",
            "yearModel",
            "mileage",
            "fuel",
            "transmission",
            "engineDisplacementLiters",
            "color",
            "priceCash",
            "shortDescription",
            "description",
            "features",
            "missingFields",
            "warnings",
          ],
        },
      },
    },
    messages: [
      {
        role: "system",
        content:
          "Extract vehicle listing fields from Portuguese car ad text. Never invent values. Use null when unknown. priceCash must be a decimal string like \"139900.00\" without currency symbol. Enums for fuel/transmission must match schema. engineDisplacementLiters is ONLY the commercial liters number (1.4, 2.0) — never TSI/Turbo/Fire Flex. If engine cannot be split safely, use null and warn. List absent fields in missingFields. Put ambiguities in warnings.",
      },
      { role: "user", content: rawText },
    ],
  });

  const content = response.choices[0]?.message?.content;
  if (!content) throw new Error("OpenAI returned empty content");
  const parsed = JSON.parse(content) as Record<string, unknown>;

  return {
    title: typeof parsed.title === "string" ? parsed.title : null,
    brand: typeof parsed.brand === "string" ? parsed.brand : null,
    model: typeof parsed.model === "string" ? parsed.model : null,
    version: typeof parsed.version === "string" ? parsed.version : null,
    yearManufacture: typeof parsed.yearManufacture === "number" ? parsed.yearManufacture : null,
    yearModel: typeof parsed.yearModel === "number" ? parsed.yearModel : null,
    mileage: typeof parsed.mileage === "number" ? parsed.mileage : null,
    fuel: asFuel(parsed.fuel),
    transmission: asTransmission(parsed.transmission),
    engineDisplacementLiters: normalizeEngineDisplacementLiters(parsed.engineDisplacementLiters),
    color: typeof parsed.color === "string" ? parsed.color : null,
    priceCash: typeof parsed.priceCash === "string" ? parsed.priceCash : null,
    shortDescription: typeof parsed.shortDescription === "string" ? parsed.shortDescription : null,
    description: typeof parsed.description === "string" ? parsed.description : null,
    features: Array.isArray(parsed.features)
      ? parsed.features.filter((x): x is string => typeof x === "string")
      : [],
    missingFields: Array.isArray(parsed.missingFields)
      ? parsed.missingFields.filter((x): x is string => typeof x === "string")
      : [],
    warnings: Array.isArray(parsed.warnings)
      ? parsed.warnings.filter((x): x is string => typeof x === "string")
      : [],
    source: "openai",
  };
}
