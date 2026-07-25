import { z } from "zod";

const userRoleEnum = z.enum(["SUPER_ADMIN", "ADMIN", "EDITOR", "LEAD_MANAGER"]);

export const createUserSchema = z.object({
  name: z.string().min(2, "Nome deve ter ao menos 2 caracteres"),
  email: z.string().email("E-mail inválido"),
  password: z.string().min(8, "Senha deve ter ao menos 8 caracteres"),
  role: userRoleEnum.default("LEAD_MANAGER"),
});

export const updateUserSchema = z.object({
  name: z.string().min(2, "Nome deve ter ao menos 2 caracteres"),
  role: userRoleEnum,
  isActive: z.boolean(),
});

export const resetPasswordSchema = z.object({
  password: z.string().min(8, "Senha deve ter ao menos 8 caracteres"),
});

export type CreateUserInput = z.infer<typeof createUserSchema>;
export type UpdateUserInput = z.infer<typeof updateUserSchema>;
export type ResetPasswordInput = z.infer<typeof resetPasswordSchema>;
