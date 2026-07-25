import { z } from "zod";

export const customerFormSchema = z.object({
  name: z.string().min(2, "Nome deve ter ao menos 2 caracteres"),
  phone: z.string().min(10, "Telefone inválido"),
  email: z
    .string()
    .email("E-mail inválido")
    .optional()
    .or(z.literal("")),
});

export type CustomerFormInput = z.infer<typeof customerFormSchema>;
