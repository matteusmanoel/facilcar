"use server";

import { sendLeadNotification } from "@/lib/email";
import { normalizePhone } from "@/features/customer/server/phone";
import { persistPublicFormLead } from "@/features/lead/server/persist-public-lead";
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
import type { LeadSource, Prisma } from "@prisma/client";

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

/** Upload de áudio opcional de lead. Retorna a URL pública ou null. */
async function uploadLeadAudio(formData: FormData): Promise<{ url: string | null; error?: string }> {
  const file = formData.get("audio");
  if (!file || typeof file === "string" || (file as File).size === 0) {
    return { url: null };
  }
  const audioFile = file as File;
  const AUDIO_MAX_BYTES = 8 * 1024 * 1024;
  if (audioFile.size > AUDIO_MAX_BYTES) {
    return { url: null, error: "O áudio deve ter no máximo 8 MB." };
  }
  if (!isVehicleStorageConfigured()) {
    // Se storage não estiver configurado, ignoramos silenciosamente o áudio
    return { url: null };
  }
  try {
    const bytes = Buffer.from(await audioFile.arrayBuffer());
    const ext = audioFile.name?.split(".").pop() ?? "webm";
    const uploaded = await uploadVehicleImageBuffer({
      bytes,
      contentType: audioFile.type || "audio/webm",
      ext,
      keyPrefix: "lead-audio",
    });
    return { url: uploaded.publicUrl };
  } catch {
    return { url: null };
  }
}

export async function createSellVehicleLead(formData: FormData): Promise<FormResult> {
  const rl = await checkRateLimit();
  if (!rl.ok) return { success: false, error: rl.error! };

  const raw = Object.fromEntries(formData.entries());
  const parsed = sellVehicleFormSchema.safeParse({
    name: raw.name,
    phone: raw.phone,
    saleMode: raw.saleMode || undefined,
    relato: raw.relato || undefined,
  });
  if (!parsed.success) {
    const firstError =
      Object.values(parsed.error.flatten().fieldErrors).flat()[0] ?? "Dados inválidos";
    return { success: false, error: firstError };
  }
  const data = parsed.data;
  const phone = normalizePhone(data.phone);

  const audioResult = await uploadLeadAudio(formData);
  if (audioResult.error) return { success: false, error: audioResult.error };

  const metadata: Prisma.JsonObject = {};
  if (audioResult.url) metadata.audioUrl = audioResult.url;

  await persistPublicFormLead({
    type: "SELL_VEHICLE",
    source: "SELL_PAGE",
    name: data.name,
    phone,
    message: data.relato || null,
    metadata: Object.keys(metadata).length > 0 ? (metadata as Prisma.InputJsonValue) : undefined,
    sell: {
      observations: data.relato,
      saleMode: data.saleMode,
    },
  });
  void sendLeadNotification({
    type: data.saleMode === "CONSIGNMENT" ? "Consignação" : "Venda direta",
    name: data.name,
    phone,
    message: data.relato ?? undefined,
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
    phone: raw.phone,
    financeMode: raw.financeMode || undefined,
    relato: raw.relato || undefined,
    vehicleId: raw.vehicleId || undefined,
    vehicleTitle: raw.vehicleTitle || undefined,
    tradeInDescription: raw.tradeInDescription || undefined,
    leadType: raw.leadType || undefined,
  });

  if (!parsed.success) {
    const firstError =
      Object.values(parsed.error.flatten().fieldErrors).flat()[0] ?? "Dados inválidos";
    return { success: false, error: firstError };
  }

  const data = parsed.data;
  const phone = normalizePhone(data.phone);

  const audioResult = await uploadLeadAudio(formData);
  if (audioResult.error) return { success: false, error: audioResult.error };

  // Tipo do lead: derivado do leadType hidden (para vendido = VEHICLE_INTEREST)
  // ou do financeMode escolhido, com fallback a FINANCING
  const leadType =
    data.leadType === "VEHICLE_INTEREST"
      ? "VEHICLE_INTEREST"
      : data.financeMode === "REFINANCING"
        ? "REFINANCING"
        : "FINANCING";

  const isSold = leadType === "VEHICLE_INTEREST";

  // Montar mensagem
  const parts: string[] = [];
  if (data.vehicleTitle) parts.push(`Veículo: ${data.vehicleTitle}`);
  if (data.financeMode === "REFINANCING") parts.push("Interesse: refinanciamento");
  if (data.relato) parts.push(data.relato);
  if (data.tradeInDescription) parts.push(`Possuo para troca: ${data.tradeInDescription}`);
  const message = parts.join(" · ") || null;

  const metadata: Prisma.JsonObject = {};
  if (audioResult.url) metadata.audioUrl = audioResult.url;
  if (data.tradeInDescription) metadata.tradeInDescription = data.tradeInDescription;
  if (data.vehicleTitle) metadata.facts = { desired_vehicle_text: data.vehicleTitle };

  await persistPublicFormLead({
    type: leadType,
    source: data.vehicleId ? "VEHICLE_PAGE" : "FINANCING_PAGE",
    name: data.name,
    phone,
    message,
    vehicleId: data.vehicleId,
    metadata: Object.keys(metadata).length > 0 ? (metadata as Prisma.InputJsonValue) : undefined,
    financing: {
      vehicleId: data.vehicleId,
      notes: message,
    },
  });

  const waNum = whatsappNumber.replace(/\D/g, "");
  let waMessage: string;
  if (isSold) {
    waMessage = `Olá, FácilCar! Meu nome é ${data.name}. Tenho interesse em um veículo similar ao que vi no site (já foi vendido).${data.relato ? ` ${data.relato}` : ""}`;
  } else if (data.financeMode === "REFINANCING") {
    waMessage = `Olá, FácilCar! Meu nome é ${data.name}. Tenho interesse em refinanciamento.${data.relato ? ` ${data.relato}` : ""}`;
  } else {
    waMessage = `Olá, FácilCar! Meu nome é ${data.name}. Tenho interesse em financiamento${data.vehicleTitle ? ` para ${data.vehicleTitle}` : ""}.${data.relato ? ` ${data.relato}` : ""}`;
  }
  const waText = encodeURIComponent(waMessage);
  const whatsappUrl = waNum ? `https://wa.me/${waNum}?text=${waText}` : "#";

  void sendLeadNotification({
    type: isSold ? "Interesse em similar" : data.financeMode === "REFINANCING" ? "Refinanciamento" : "Financiamento",
    name: data.name,
    phone: data.phone,
    vehicleTitle: data.vehicleTitle ?? undefined,
    message: message ?? undefined,
  });

  return { success: true, whatsappUrl };
}
