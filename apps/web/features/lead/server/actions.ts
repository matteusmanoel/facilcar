"use server";

import { prisma } from "@/lib/db";
import { sendLeadNotification } from "@/lib/email";
import { upsertCustomerByPhone } from "@/features/customer/server/upsert";
import { normalizePhone } from "@/features/customer/server/phone";
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
  const customer = await upsertCustomerByPhone(name, phone, email);

  await prisma.lead.create({
    data: {
      type: "CONTACT",
      status: "NEW",
      source: "CONTACT_PAGE",
      channel: "FORM",
      name,
      phone,
      email: email || null,
      message: message || null,
      originUrl: null,
      customerId: customer?.id ?? null,
    },
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
  const customer = await upsertCustomerByPhone(name, phone, email);

  await prisma.lead.create({
    data: {
      type: "VEHICLE_INTEREST",
      status: "NEW",
      source,
      channel: "FORM",
      name,
      phone,
      email: email || null,
      message: message || null,
      vehicleId,
      originUrl: null,
      customerId: customer?.id ?? null,
    },
  });
  const vehicle = await prisma.vehicle.findUnique({ where: { id: vehicleId }, select: { title: true } });
  void sendLeadNotification({ type: "Interesse em veículo", name, phone, email, message, vehicleTitle: vehicle?.title ?? undefined });
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
  const customer = await upsertCustomerByPhone(data.name, data.phone, data.email);

  const lead = await prisma.lead.create({
    data: {
      type: "FINANCING",
      status: "NEW",
      source: "FINANCING_PAGE",
      channel: "FORM",
      name: data.name,
      phone: data.phone,
      email: data.email || null,
      message: data.notes || null,
      vehicleId: data.vehicleId || null,
      originUrl: null,
      customerId: customer?.id ?? null,
    },
  });

  await prisma.financingRequest.create({
    data: {
      leadId: lead.id,
      vehicleId: data.vehicleId || null,
      hasDriverLicense: data.hasDriverLicense,
      monthlyIncome: data.monthlyIncome ?? null,
      downPayment: data.downPayment ?? null,
      desiredInstallments: data.desiredInstallments ?? null,
      notes: data.notes || null,
    },
  });
  void sendLeadNotification({ type: "Financiamento", name: data.name, phone: data.phone, email: data.email, message: data.notes });
  return { success: true };
}

const SELL_PHOTO_MAX_FILES = 5;
const SELL_PHOTO_MAX_BYTES = 4 * 1024 * 1024;
const SELL_PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function sellPhotoExt(contentType: string): string {
  if (contentType === "image/png") return "png";
  if (contentType === "image/webp") return "webp";
  return "jpg";
}

async function uploadSellPhotos(formData: FormData): Promise<{ urls: string[]; error?: string }> {
  const files = formData
    .getAll("photos")
    .filter((entry): entry is File => entry instanceof File && entry.size > 0);

  if (files.length === 0) return { urls: [] };
  if (files.length > SELL_PHOTO_MAX_FILES) {
    return { urls: [], error: `Envie no máximo ${SELL_PHOTO_MAX_FILES} fotos.` };
  }
  if (!isVehicleStorageConfigured()) {
    return { urls: [], error: "Upload de fotos indisponível no momento. Envie o formulário sem imagens ou tente de novo." };
  }

  const urls: string[] = [];
  for (const file of files) {
    if (!SELL_PHOTO_TYPES.has(file.type) || file.size > SELL_PHOTO_MAX_BYTES) {
      return {
        urls: [],
        error: "Use JPEG, PNG ou WebP de até 4 MB por foto.",
      };
    }
    const bytes = Buffer.from(await file.arrayBuffer());
    const uploaded = await uploadVehicleImageBuffer({
      bytes,
      contentType: file.type,
      ext: sellPhotoExt(file.type),
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

  const customer = await upsertCustomerByPhone(data.name, phone);

  const lead = await prisma.lead.create({
    data: {
      type: "SELL_VEHICLE",
      status: "NEW",
      source: "SELL_PAGE",
      channel: "FORM",
      name: data.name,
      phone,
      email: null,
      message: data.observations || null,
      originUrl: null,
      customerId: customer?.id ?? null,
    },
  });

  await prisma.sellRequest.create({
    data: {
      leadId: lead.id,
      brand: data.brand || null,
      model: data.model || null,
      version: data.version || null,
      yearManufacture: data.yearManufacture ?? null,
      yearModel: data.yearModel ?? null,
      mileage: data.mileage ?? null,
      fuelType: data.fuelType || null,
      transmission: data.transmission || null,
      observations: data.observations || null,
      saleMode: data.saleMode || null,
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

  // Basic deduplication: same phone + vehicleId within 24h
  const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000);
  const existing = await prisma.lead.findFirst({
    where: {
      phone,
      vehicleId: data.vehicleId ?? null,
      type: "FINANCING",
      deletedAt: null,
      createdAt: { gte: cutoff },
    },
    select: { id: true },
  });

  const vehicleLabel =
    data.vehicleTitle ||
    [data.vehicleModel, data.vehicleYear].filter(Boolean).join(" ") ||
    "veículo de interesse";

  const waNum = whatsappNumber.replace(/\D/g, "");
  const waText = encodeURIComponent(
    `Olá, FácilCar! Meu nome é ${data.name}. Tenho interesse em financiar: ${vehicleLabel}. Renda mensal: R$ ${Number(data.monthlyIncome).toLocaleString("pt-BR")}. Entrada: R$ ${Number(data.downPayment).toLocaleString("pt-BR")}. Prazo: ${data.desiredInstallments} meses. Aguardo análise!`,
  );
  const whatsappUrl = waNum ? `https://wa.me/${waNum}?text=${waText}` : "#";

  if (existing) {
    console.log(`[leads] duplicate skipped phone=${phone} vehicleId=${data.vehicleId}`);
    return { success: true, whatsappUrl };
  }

  const source: LeadSource = data.vehicleId ? "VEHICLE_PAGE" : "FINANCING_PAGE";
  const customer = await upsertCustomerByPhone(data.name, phone);

  const lead = await prisma.lead.create({
    data: {
      type: "FINANCING",
      status: "QUALIFIED",
      source,
      channel: "FORM",
      name: data.name,
      phone,
      message: null,
      vehicleId: data.vehicleId || null,
      originUrl: null,
      customerId: customer?.id ?? null,
    },
  });

  await prisma.financingRequest.create({
    data: {
      leadId: lead.id,
      vehicleId: data.vehicleId || null,
      cpf: data.cpf,
      birthDate: data.birthDate ? new Date(data.birthDate) : null,
      monthlyIncome: data.monthlyIncome,
      downPayment: data.downPayment,
      desiredInstallments: data.desiredInstallments,
      vehicleYear: data.vehicleYear ?? null,
      vehicleModel: data.vehicleModel ?? null,
      hasDriverLicense: null,
      notes: null,
    },
  });

  void sendLeadNotification({
    type: "Simulação de Financiamento",
    name: data.name,
    phone: data.phone,
    vehicleTitle: vehicleLabel,
    message: `Renda: R$ ${Number(data.monthlyIncome).toLocaleString("pt-BR")} | Entrada: R$ ${Number(data.downPayment).toLocaleString("pt-BR")} | Prazo: ${data.desiredInstallments}m`,
  });

  return { success: true, whatsappUrl };
}
