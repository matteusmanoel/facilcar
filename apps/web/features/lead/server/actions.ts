"use server";

import { sendLeadNotification } from "@/lib/email";
import { normalizePhone } from "@/features/customer/server/phone";
import { persistPublicFormLead } from "@/features/lead/server/persist-public-lead";
import {
  collectSellPhotoUploads,
  inferSellPhotoContentType,
  SELL_PHOTO_MAX_BYTES,
  SELL_PHOTO_MAX_FILES,
  sellPhotoExt,
} from "@/features/lead/lib/sell-photos";
import { uploadVehicleImageBuffer } from "@/features/storage/server/upload-vehicle-image";
import { isVehicleStorageConfigured } from "@/features/storage/server/s3-client";
import {
  contactFormSchema,
  vehicleInterestFormSchema,
  financingFormSchema,
  financingSimulationSchema,
  sellVehicleFormSchema,
} from "@/schemas/lead";
import { checkRateLimit } from "./rateLimit";
import type { LeadSource } from "@prisma/client";

type FormResult = { success: true } | { success: false; error: string };
type SimulationResult = { success: true; whatsappUrl: string } | { success: false; error: string };

export async function createContactLead(formData: FormData): Promise<FormResult> {
  const rl = await checkRateLimit();
  if (!rl.ok) return { success: false, error: rl.error! };

  const raw = Object.fromEntries(formData.entries());
  const parsed = contactFormSchema.safeParse({
    name: raw.name,
    phone: raw.phone,
    email: raw.email || undefined,
    message: raw.message || undefined,
  });
  if (!parsed.success) {
    return { success: false, error: parsed.error.flatten().fieldErrors?.name?.[0] ?? "Dados inválidos" };
  }
  const { name, phone, email, message } = parsed.data;
  await persistPublicFormLead({
    type: "CONTACT",
    source: "CONTACT_PAGE",
    name,
    phone,
    email,
    message,
  });
  void sendLeadNotification({ type: "Contato", name, phone, email, message });
  return { success: true };
}

export async function createVehicleInterestLead(
  formData: FormData,
  vehicleId: string,
  source: LeadSource = "VEHICLE_PAGE"
): Promise<FormResult> {
  const rl = await checkRateLimit();
  if (!rl.ok) return { success: false, error: rl.error! };

  const raw = Object.fromEntries(formData.entries());
  const parsed = vehicleInterestFormSchema.safeParse({
    ...raw,
    vehicleId,
  });
  if (!parsed.success) {
    return { success: false, error: parsed.error.flatten().fieldErrors?.name?.[0] ?? "Dados inválidos" };
  }
  const { name, phone, email, message } = parsed.data;
  await persistPublicFormLead({
    type: "VEHICLE_INTEREST",
    source,
    name,
    phone,
    email,
    message,
    vehicleId,
  });
  void sendLeadNotification({ type: "Interesse em veículo", name, phone, email, message });
  return { success: true };
}

export async function createFinancingLead(formData: FormData): Promise<FormResult> {
  const raw = Object.fromEntries(formData.entries());
  const parsed = financingFormSchema.safeParse({
    name: raw.name,
    phone: raw.phone,
    email: raw.email || undefined,
    hasDriverLicense: raw.hasDriverLicense === "true" || raw.hasDriverLicense === "sim",
    monthlyIncome: raw.monthlyIncome ? Number(raw.monthlyIncome) : undefined,
    downPayment: raw.downPayment ? Number(raw.downPayment) : undefined,
    desiredInstallments: raw.desiredInstallments ? Number(raw.desiredInstallments) : undefined,
    notes: raw.notes || undefined,
    vehicleId: raw.vehicleId || undefined,
  });
  if (!parsed.success) {
    return { success: false, error: parsed.error.flatten().fieldErrors?.name?.[0] ?? "Dados inválidos" };
  }
  const data = parsed.data;
  await persistPublicFormLead({
    type: "FINANCING",
    source: "FINANCING_PAGE",
    name: data.name,
    phone: data.phone,
    email: data.email,
    message: data.notes,
    vehicleId: data.vehicleId,
    financing: {
      vehicleId: data.vehicleId,
      hasDriverLicense: data.hasDriverLicense,
      monthlyIncome: data.monthlyIncome ?? null,
      downPayment: data.downPayment ?? null,
      desiredInstallments: data.desiredInstallments ?? null,
      notes: data.notes,
    },
  });
  void sendLeadNotification({ type: "Financiamento", name: data.name, phone: data.phone, email: data.email, message: data.notes });
  return { success: true };
}

async function uploadSellPhotos(formData: FormData): Promise<{ urls: string[]; error?: string }> {
  const files = collectSellPhotoUploads(formData);

  if (files.length === 0) return { urls: [] };
  if (files.length > SELL_PHOTO_MAX_FILES) {
    return { urls: [], error: `Envie no máximo ${SELL_PHOTO_MAX_FILES} fotos.` };
  }
  if (!isVehicleStorageConfigured()) {
    return { urls: [], error: "Upload de fotos indisponível no momento. Envie o formulário sem imagens ou tente de novo." };
  }

  const urls: string[] = [];
  for (const file of files) {
    if (file.size > SELL_PHOTO_MAX_BYTES) {
      return {
        urls: [],
        error: "Use JPEG, PNG ou WebP de até 4 MB por foto.",
      };
    }
    const bytes = Buffer.from(await file.arrayBuffer());
    const contentType = inferSellPhotoContentType(file, bytes);
    if (!contentType) {
      return {
        urls: [],
        error: "Use JPEG, PNG ou WebP de até 4 MB por foto.",
      };
    }
    const uploaded = await uploadVehicleImageBuffer({
      bytes,
      contentType,
      ext: sellPhotoExt(contentType),
      keyPrefix: "sell-leads",
    });
    urls.push(uploaded.publicUrl);
  }
  return { urls };
}

export async function createSellVehicleLead(formData: FormData): Promise<FormResult> {
  const rl = await checkRateLimit();
  if (!rl.ok) return { success: false, error: rl.error! };

  const raw = Object.fromEntries(formData.entries());
  const parsed = sellVehicleFormSchema.safeParse({
    name: raw.name,
    phone: raw.phone,
    observations: raw.observations || undefined,
    brand: raw.brand || undefined,
    model: raw.model || undefined,
    version: raw.version || undefined,
    yearManufacture: raw.yearManufacture ? Number(raw.yearManufacture) : undefined,
    yearModel: raw.yearModel ? Number(raw.yearModel) : undefined,
    mileage: raw.mileage ? Number(raw.mileage) : undefined,
    fuelType: raw.fuelType || undefined,
    transmission: raw.transmission || undefined,
    saleMode: raw.saleMode || undefined,
  });
  if (!parsed.success) {
    const firstError =
      Object.values(parsed.error.flatten().fieldErrors).flat()[0] ?? "Dados inválidos";
    return { success: false, error: firstError };
  }
  const data = parsed.data;
  const phone = normalizePhone(data.phone);

  let photoUrls: string[] = [];
  try {
    const uploaded = await uploadSellPhotos(formData);
    if (uploaded.error) return { success: false, error: uploaded.error };
    photoUrls = uploaded.urls;
  } catch {
    return { success: false, error: "Não foi possível enviar as fotos. Tente novamente." };
  }

  const vehicleLabel = [data.brand, data.model].filter(Boolean).join(" ");

  await persistPublicFormLead({
    type: "SELL_VEHICLE",
    source: "SELL_PAGE",
    name: data.name,
    phone,
    message: data.observations || vehicleLabel || null,
    metadata: vehicleLabel
      ? { facts: { desired_vehicle_text: vehicleLabel } }
      : undefined,
    sell: {
      brand: data.brand,
      model: data.model,
      version: data.version,
      yearManufacture: data.yearManufacture,
      yearModel: data.yearModel,
      mileage: data.mileage,
      fuelType: data.fuelType,
      transmission: data.transmission,
      observations: data.observations,
      saleMode: data.saleMode,
      photoUrls,
    },
  });
  void sendLeadNotification({
    type: "Vender veículo",
    name: data.name,
    phone,
    message: data.observations ?? undefined,
  });
  return { success: true };
}

export async function createFinancingSimulationLead(
  formData: FormData,
  whatsappNumber: string,
): Promise<SimulationResult> {
  const rl = await checkRateLimit();
  if (!rl.ok) return { success: false, error: rl.error! };

  const raw = Object.fromEntries(formData.entries());

  const parsed = financingSimulationSchema.safeParse({
    name: raw.name,
    cpf: raw.cpf,
    birthDate: raw.birthDate,
    phone: raw.phone,
    monthlyIncome: raw.monthlyIncome ? Number(raw.monthlyIncome) : undefined,
    downPayment: raw.downPayment !== undefined ? Number(raw.downPayment) : 0,
    desiredInstallments: raw.desiredInstallments ? Number(raw.desiredInstallments) : undefined,
    vehicleYear: raw.vehicleYear ? Number(raw.vehicleYear) : undefined,
    vehicleModel: raw.vehicleModel || undefined,
    vehicleId: raw.vehicleId || undefined,
    vehicleTitle: raw.vehicleTitle || undefined,
  });

  if (!parsed.success) {
    const firstError =
      Object.values(parsed.error.flatten().fieldErrors).flat()[0] ?? "Dados inválidos";
    return { success: false, error: firstError };
  }

  const data = parsed.data;
  const phone = normalizePhone(data.phone);

  const vehicleLabel =
    data.vehicleTitle ||
    [data.vehicleModel, data.vehicleYear].filter(Boolean).join(" ") ||
    null;

  const summary = [
    vehicleLabel ? `Veículo: ${vehicleLabel}` : null,
    `Renda: R$ ${Number(data.monthlyIncome).toLocaleString("pt-BR")}`,
    `Entrada: R$ ${Number(data.downPayment).toLocaleString("pt-BR")}`,
    `Prazo: ${data.desiredInstallments} meses`,
  ]
    .filter(Boolean)
    .join(" · ");

  await persistPublicFormLead({
    type: "FINANCING",
    source: data.vehicleId ? "VEHICLE_PAGE" : "FINANCING_PAGE",
    name: data.name,
    phone,
    message: summary,
    vehicleId: data.vehicleId,
    metadata: vehicleLabel
      ? { facts: { desired_vehicle_text: vehicleLabel } }
      : undefined,
    financing: {
      vehicleId: data.vehicleId,
      cpf: data.cpf,
      birthDate: data.birthDate ? new Date(data.birthDate) : null,
      monthlyIncome: data.monthlyIncome,
      downPayment: data.downPayment,
      desiredInstallments: data.desiredInstallments,
      vehicleYear: data.vehicleYear ?? null,
      vehicleModel: data.vehicleModel ?? null,
    },
  });

  const waNum = whatsappNumber.replace(/\D/g, "");
  const waText = encodeURIComponent(
    `Olá, FácilCar! Meu nome é ${data.name}. Tenho interesse em financiar: ${vehicleLabel || "veículo de interesse"}. Renda mensal: R$ ${Number(data.monthlyIncome).toLocaleString("pt-BR")}. Entrada: R$ ${Number(data.downPayment).toLocaleString("pt-BR")}. Prazo: ${data.desiredInstallments} meses. Aguardo análise!`,
  );
  const whatsappUrl = waNum ? `https://wa.me/${waNum}?text=${waText}` : "#";

  void sendLeadNotification({
    type: "Simulação de Financiamento",
    name: data.name,
    phone: data.phone,
    vehicleTitle: vehicleLabel ?? undefined,
    message: summary,
  });

  return { success: true, whatsappUrl };
}
