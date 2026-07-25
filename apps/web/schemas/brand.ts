import { z } from "zod";

export const createBrandSchema = z.object({
  name: z.string().min(1, "Nome é obrigatório"),
  slug: z
    .string()
    .min(1, "Slug é obrigatório")
    .regex(/^[a-z0-9-]+$/, "Slug deve conter apenas letras minúsculas, números e hífens"),
  logoUrl: z.string().url("URL inválida").optional().or(z.literal("")),
  isActive: z.boolean().default(true),
});

export const updateBrandSchema = createBrandSchema;

export type CreateBrandInput = z.infer<typeof createBrandSchema>;
export type UpdateBrandInput = z.infer<typeof updateBrandSchema>;
