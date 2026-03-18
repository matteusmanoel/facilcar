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
  desiredInstallments: z.coerce.number().int().min(1).max(84).optional(),
  notes: z.string().max(2000).optional(),
  vehicleId: z.string().optional(),
});

export const sellVehicleFormSchema = z.object({
  name: z.string().min(2, "Nome deve ter ao menos 2 caracteres"),
  phone: z.string().min(10, "Telefone inválido").regex(phoneRegex, "Telefone inválido"),
  email: z.string().email("E-mail inválido").optional().or(z.literal("")),
  observations: z.string().max(2000).optional(),
  brand: z.string().optional(),
  model: z.string().optional(),
  version: z.string().optional(),
  yearManufacture: z.coerce.number().int().min(1900).max(2100).optional(),
  yearModel: z.coerce.number().int().min(1900).max(2100).optional(),
  mileage: z.coerce.number().int().min(0).optional(),
  fuelType: z.string().optional(),
  transmission: z.string().optional(),
});

export type ContactFormValues = z.infer<typeof contactFormSchema>;
export type VehicleInterestFormValues = z.infer<typeof vehicleInterestFormSchema>;
export type FinancingFormValues = z.infer<typeof financingFormSchema>;
export type SellVehicleFormValues = z.infer<typeof sellVehicleFormSchema>;
