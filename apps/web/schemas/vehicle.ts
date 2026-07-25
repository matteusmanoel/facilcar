import { z } from "zod";

const vehicleStatusEnum = z.enum(["DRAFT", "PUBLISHED", "RESERVED", "SOLD", "ARCHIVED"]);
const vehicleTypeEnum = z.enum(["CAR", "MOTORCYCLE", "UTILITY", "OTHER"]);
const fuelTypeEnum = z.enum(
  ["GASOLINE", "ETHANOL", "FLEX", "DIESEL", "ELECTRIC", "HYBRID", "OTHER"],
  { message: "Combustível é obrigatório" },
);
const transmissionEnum = z.enum(["MANUAL", "AUTOMATIC", "AUTOMATED", "CVT", "OTHER"], {
  message: "Câmbio é obrigatório",
});

function emptyToUndefined(value: unknown) {
  if (value === "" || value === null || value === undefined) return undefined;
  if (typeof value === "number" && Number.isNaN(value)) return undefined;
  return value;
}

function optionalIntField(message: string, min: number, max: number) {
  return z.preprocess(
    emptyToUndefined,
    z.coerce
      .number({ message })
      .int(message)
      .min(min, message)
      .max(max, message)
      .optional(),
  );
}

function optionalNonNegativeInt(message: string) {
  return z.preprocess(
    emptyToUndefined,
    z.coerce.number({ message }).int(message).min(0, message).optional(),
  );
}

export const createVehicleSchema = z.object({
  slug: z
    .string()
    .regex(/^[a-z0-9-]*$/, "Slug: apenas minúsculas, números e hífens")
    .optional(),
  status: vehicleStatusEnum,
  type: vehicleTypeEnum,
  title: z.string().min(1, "Título é obrigatório"),
  shortDescription: z.string().optional(),
  description: z.string().optional(),
  brandId: z.string().min(1, "Marca é obrigatória"),
  model: z.string().min(1, "Modelo é obrigatório"),
  version: z.string().optional(),
  yearManufacture: optionalIntField("Ano de fabricação inválido", 1900, 2100),
  yearModel: optionalIntField("Ano modelo inválido", 1900, 2100),
  mileage: optionalNonNegativeInt("Quilometragem inválida"),
  fuelType: fuelTypeEnum,
  transmission: transmissionEnum,
  color: z.string().optional(),
  doors: optionalNonNegativeInt("Número de portas inválido"),
  plateFinal: z.string().max(1, "Use apenas um caractere").optional(),
  priceCash: z.preprocess(
    emptyToUndefined,
    z.coerce
      .number({ message: "Preço à vista é obrigatório" })
      .min(0, "Preço à vista inválido"),
  ),
  priceTradeIn: z.coerce.number({ message: "Preço inválido" }).min(0, "Preço inválido").optional(),
  pricePromotional: z.coerce.number({ message: "Preço inválido" }).min(0, "Preço inválido").optional(),
  city: z.string().optional(),
  state: z.string().optional(),
  featured: z.boolean().optional(),
  aceitaTroca: z.boolean().optional(),
  aceitaSemEntrada: z.boolean().optional(),
  parcelaBase: z.coerce.number({ message: "Valor inválido" }).min(0, "Valor inválido").optional(),
  entradaMinima: z.coerce.number({ message: "Valor inválido" }).min(0, "Valor inválido").optional(),
  rendaMinimaSugerida: z.coerce.number({ message: "Valor inválido" }).min(0, "Valor inválido").optional(),
  prioridade: z.coerce
    .number({ message: "Prioridade inválida" })
    .int("Prioridade inválida")
    .min(0, "Prioridade inválida")
    .optional(),
  metaTitle: z.string().optional(),
  metaDescription: z.string().optional(),
  imageUrls: z.string().optional(), // one URL per line
  features: z.string().optional(),  // one label per line
});

export type CreateVehicleInput = z.infer<typeof createVehicleSchema>;

export const updateVehicleSchema = createVehicleSchema.partial().extend({
  id: z.string().min(1, "ID é obrigatório"),
});
export type UpdateVehicleInput = z.infer<typeof updateVehicleSchema>;
