import { z } from "zod";

/** Inline brand create — only the display name is required. */
export const createBrandInlineSchema = z.object({
  name: z.string().trim().min(1, "Nome é obrigatório").max(80, "Nome muito longo"),
});

export type CreateBrandInlineInput = z.infer<typeof createBrandInlineSchema>;
