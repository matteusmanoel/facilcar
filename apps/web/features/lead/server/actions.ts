"use server";

import { prisma } from "@/lib/db";
import { sendLeadNotification } from "@/lib/email";
import {
  contactFormSchema,
  vehicleInterestFormSchema,
  financingFormSchema,
  sellVehicleFormSchema,
} from "@/schemas/lead";
import type { $Enums } from "@prisma/client";

type FormResult = { success: true } | { success: false; error: string };

function getOriginUrl(): string | null {
  if (typeof window !== "undefined") return window.location.href;
  return null;
}

export async function createContactLead(formData: FormData): Promise<FormResult> {
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
    },
  });
  void sendLeadNotification({ type: "Contato", name, phone, email, message });
  return { success: true };
}

export async function createVehicleInterestLead(
  formData: FormData,
  vehicleId: string,
  source: $Enums.LeadSource = "VEHICLE_PAGE"
): Promise<FormResult> {
  const raw = Object.fromEntries(formData.entries());
  const parsed = vehicleInterestFormSchema.safeParse({
    ...raw,
    vehicleId,
  });
  if (!parsed.success) {
    return { success: false, error: parsed.error.flatten().fieldErrors?.name?.[0] ?? "Dados inválidos" };
  }
  const { name, phone, email, message } = parsed.data;

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

export async function createSellVehicleLead(formData: FormData): Promise<FormResult> {
  const raw = Object.fromEntries(formData.entries());
  const parsed = sellVehicleFormSchema.safeParse({
    name: raw.name,
    phone: raw.phone,
    email: raw.email || undefined,
    observations: raw.observations || undefined,
    brand: raw.brand || undefined,
    model: raw.model || undefined,
    version: raw.version || undefined,
    yearManufacture: raw.yearManufacture ? Number(raw.yearManufacture) : undefined,
    yearModel: raw.yearModel ? Number(raw.yearModel) : undefined,
    mileage: raw.mileage ? Number(raw.mileage) : undefined,
    fuelType: raw.fuelType || undefined,
    transmission: raw.transmission || undefined,
  });
  if (!parsed.success) {
    return { success: false, error: parsed.error.flatten().fieldErrors?.name?.[0] ?? "Dados inválidos" };
  }
  const data = parsed.data;

  const lead = await prisma.lead.create({
    data: {
      type: "SELL_VEHICLE",
      status: "NEW",
      source: "SELL_PAGE",
      channel: "FORM",
      name: data.name,
      phone: data.phone,
      email: data.email || null,
      message: data.observations || null,
      originUrl: null,
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
    },
  });
  void sendLeadNotification({ type: "Vender veículo", name: data.name, phone: data.phone, email: data.email, message: data.observations ?? undefined });
  return { success: true };
}
