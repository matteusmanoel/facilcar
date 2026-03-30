import { z } from "zod";

const vehicleStatusEnum = z.enum(["DRAFT", "PUBLISHED", "RESERVED", "SOLD", "ARCHIVED"]);
const vehicleTypeEnum = z.enum(["CAR", "MOTORCYCLE", "UTILITY", "OTHER"]);
const fuelTypeEnum = z.enum(["GASOLINE", "ETHANOL", "FLEX", "DIESEL", "ELECTRIC", "HYBRID", "OTHER"]);
const transmissionEnum = z.enum(["MANUAL", "AUTOMATIC", "AUTOMATED", "CVT", "OTHER"]);

export const createVehicleSchema = z.object({
  slug: z
    .string()
    .regex(/^[a-z0-9-]*$/, "Slug: apenas minúsculas, números e hífens")
    .optional(),
  status: vehicleStatusEnum,
  type: vehicleTypeEnum,
  title: z.string().min(1),
  shortDescription: z.string().optional(),
  description: z.string().optional(),
  brandId: z.string().min(1),
  model: z.string().min(1),
  version: z.string().optional(),
  yearManufacture: z.coerce.number().int().min(1900).max(2100).optional(),
  yearModel: z.coerce.number().int().min(1900).max(2100).optional(),
  mileage: z.coerce.number().int().min(0).optional(),
  fuelType: fuelTypeEnum.optional(),
  transmission: transmissionEnum.optional(),
  color: z.string().optional(),
  doors: z.coerce.number().int().min(0).optional(),
  priceCash: z.coerce.number().min(0).optional(),
  priceTradeIn: z.coerce.number().min(0).optional(),
  pricePromotional: z.coerce.number().min(0).optional(),
  city: z.string().optional(),
  state: z.string().optional(),
  featured: z.boolean().optional(),
  metaTitle: z.string().optional(),
  metaDescription: z.string().optional(),
  imageUrls: z.string().optional(), // one URL per line
  features: z.string().optional(),  // one label per line
});

export type CreateVehicleInput = z.infer<typeof createVehicleSchema>;

export const updateVehicleSchema = createVehicleSchema.partial().extend({
  id: z.string().min(1),
});
export type UpdateVehicleInput = z.infer<typeof updateVehicleSchema>;
