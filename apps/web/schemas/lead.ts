import { z } from "zod";

const phoneRegex = /^[\d\s\-\(\)\+]+$/;

export const contactFormSchema = z.object({
  name: z.string().min(2, "Nome deve ter ao menos 2 caracteres"),
  phone: z.string().min(10, "Telefone inválido").regex(phoneRegex, "Telefone inválido"),
  email: z.string().email("E-mail inválido").optional().or(z.literal("")),
  message: z.string().max(2000).optional(),
});

export const vehicleInterestFormSchema = contactFormSchema.extend({
  vehicleId: z.string().min(1, "Veículo é obrigatório"),
});

export const financingFormSchema = z.object({
  name: z.string().min(2, "Nome deve ter ao menos 2 caracteres"),
  phone: z.string().min(10, "Telefone inválido").regex(phoneRegex, "Telefone inválido"),
  email: z.string().email("E-mail inválido").optional().or(z.literal("")),
  hasDriverLicense: z.boolean(),
  monthlyIncome: z.coerce.number().min(0).optional(),
  downPayment: z.coerce.number().min(0).optional(),
  desiredInstallments: z.coerce
    .number({ message: "Número de parcelas inválido" })
    .int("Número de parcelas inválido")
    .min(1, "Informe ao menos 1 parcela")
    .max(84, "Máximo de 84 parcelas")
    .optional(),
  notes: z.string().max(2000).optional(),
  vehicleId: z.string().optional(),
});

export const financingSimulationSchema = z.object({
  name: z.string().min(2, "Nome deve ter ao menos 2 caracteres"),
  cpf: z.string().min(11, "CPF inválido").max(14, "CPF inválido"),
  birthDate: z.string().min(1, "Data de nascimento é obrigatória"),
  phone: z.string().min(10, "Telefone inválido").regex(phoneRegex, "Telefone inválido"),
  monthlyIncome: z.coerce.number().min(1, "Informe sua renda mensal"),
  downPayment: z.coerce.number().min(0, "Valor de entrada inválido"),
  desiredInstallments: z.coerce
    .number({ message: "Número de parcelas inválido" })
    .int("Número de parcelas inválido")
    .min(1, "Informe ao menos 1 parcela")
    .max(84, "Máximo de 84 parcelas"),
  vehicleYear: z.coerce.number().int().min(1990).max(2030).optional(),
  vehicleModel: z.string().optional(),
  vehicleId: z.string().optional(),
  vehicleTitle: z.string().optional(),
});

export type FinancingSimulationValues = z.infer<typeof financingSimulationSchema>;

export const sellVehicleFormSchema = z.object({
  name: z.string().min(2, "Nome deve ter ao menos 2 caracteres"),
  phone: z.string().min(10, "Telefone inválido").regex(phoneRegex, "Telefone inválido"),
  observations: z.string().max(2000).optional(),
  brand: z.string().optional(),
  model: z.string().optional(),
  version: z.string().optional(),
  yearManufacture: z.coerce.number().int().min(1900).max(2100).optional(),
  yearModel: z.coerce.number().int().min(1900).max(2100).optional(),
  mileage: z.coerce.number().int().min(0).optional(),
  fuelType: z.string().optional(),
  transmission: z.string().optional(),
  saleMode: z.enum(["CONSIGNMENT", "DIRECT_PURCHASE"]).optional(),
});

const leadTypeEnum = z.enum([
  "CONTACT",
  "VEHICLE_INTEREST",
  "FINANCING",
  "SELL_VEHICLE",
  "REFINANCING",
  "TRADE_IN",
  "CONSIGNMENT",
  "THIRD_PARTY_FINANCING",
]);

export const createManualLeadSchema = z.object({
  name: z.string().min(2, "Nome deve ter ao menos 2 caracteres"),
  phone: z.string().min(10, "Telefone inválido").regex(phoneRegex, "Telefone inválido"),
  email: z.string().email("E-mail inválido").optional().or(z.literal("")),
  type: leadTypeEnum,
  message: z.string().max(2000).optional(),
  vehicleId: z.string().optional(),
  nameResolution: z.enum(["keep_existing", "use_new"]).optional(),
});

export type CreateManualLeadInput = z.infer<typeof createManualLeadSchema>;

export const updateLeadContactSchema = z.object({
  leadId: z.string().min(1),
  name: z.string().min(2, "Nome deve ter ao menos 2 caracteres"),
  phone: z.string().min(10, "Telefone inválido").regex(phoneRegex, "Telefone inválido"),
  email: z.string().email("E-mail inválido").optional().or(z.literal("")),
  city: z.string().max(80).optional().or(z.literal("")),
  state: z.string().max(2).optional().or(z.literal("")),
  cpf: z.string().max(14).optional().or(z.literal("")),
  cpfTouched: z.boolean().optional(),
  birthDate: z
    .string()
    .optional()
    .or(z.literal(""))
    .refine((v) => !v || /^\d{4}-\d{2}-\d{2}$/.test(v), "Data inválida"),
  nameResolution: z.enum(["keep_existing", "use_new"]).optional(),
});

export const updateLeadFinancingSchema = z.object({
  leadId: z.string().min(1),
  monthlyIncome: z.string().optional().or(z.literal("")),
  downPayment: z.string().optional().or(z.literal("")),
  desiredInstallments: z.string().optional().or(z.literal("")),
  hasDriverLicense: z.enum(["", "true", "false"]).optional(),
  occupation: z.string().max(120).optional().or(z.literal("")),
  notes: z.string().max(2000).optional().or(z.literal("")),
});

export const updateLeadSellSchema = z.object({
  leadId: z.string().min(1),
  brand: z.string().max(80).optional().or(z.literal("")),
  model: z.string().max(80).optional().or(z.literal("")),
  version: z.string().max(80).optional().or(z.literal("")),
  yearManufacture: z.string().optional().or(z.literal("")),
  yearModel: z.string().optional().or(z.literal("")),
  mileage: z.string().optional().or(z.literal("")),
  fuelType: z.string().max(40).optional().or(z.literal("")),
  transmission: z.string().max(40).optional().or(z.literal("")),
  saleMode: z.enum(["", "CONSIGNMENT", "DIRECT_PURCHASE"]).optional(),
  observations: z.string().max(2000).optional().or(z.literal("")),
});

export type UpdateLeadContactInput = z.infer<typeof updateLeadContactSchema>;
export type UpdateLeadFinancingInput = z.infer<typeof updateLeadFinancingSchema>;
export type UpdateLeadSellInput = z.infer<typeof updateLeadSellSchema>;

export type ContactFormValues = z.infer<typeof contactFormSchema>;
export type VehicleInterestFormValues = z.infer<typeof vehicleInterestFormSchema>;
export type FinancingFormValues = z.infer<typeof financingFormSchema>;
export type SellVehicleFormValues = z.infer<typeof sellVehicleFormSchema>;
