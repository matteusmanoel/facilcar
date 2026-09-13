"use server";

import { revalidatePath } from "next/cache";
import type { LeadStatus } from "@prisma/client";
import {
  ForbiddenError,
  LEAD_ROLES,
  UnauthorizedError,
  requireAdminRole,
} from "@/features/auth/server/rbac";
import { resolveCustomerForLead } from "@/features/customer/server/upsert";
import { normalizePhone } from "@/features/customer/server/phone";
import { createManualLeadSchema, updateLeadContactSchema, updateLeadFinancingSchema, updateLeadSellSchema } from "@/schemas/lead";
import { prisma } from "@/lib/db";
import { digitsOnly, formatCPF } from "@/lib/input-masks";
import {
  isInvalidNumber,
  parseDateInputValue,
  parseOptionalInt,
  parseOptionalNumber,
} from "@/features/lead/lib/edit-values";
import { nextPrimaryVehicleId } from "@/features/lead/lib/vehicle-label";
import {
  claimLeadAction as claimLeadFromOwnership,
  resumeConversationAction as resumeConversationFromOwnership,
} from "./conversation-ownership";

export async function claimLeadAction(leadId: string, clientOwnerId?: unknown) {
  return claimLeadFromOwnership(leadId, clientOwnerId);
}

export async function resumeConversationAction(leadId: string, reason?: string) {
  return resumeConversationFromOwnership(leadId, reason);
}

const NOT_DELETED = { deletedAt: null } as const;

const VALID_STATUSES: LeadStatus[] = [
  "NEW",
  "IN_PROGRESS",
  "CONTACTED",
  "QUALIFIED",
  "WON",
  "LOST",
  "SPAM",
];

function handleAuthError(e: unknown) {
  if (e instanceof UnauthorizedError) return { ok: false as const, error: e.message };
  if (e instanceof ForbiddenError) return { ok: false as const, error: e.message };
  throw e;
}

async function requireLeadManager() {
  return requireAdminRole(LEAD_ROLES);
}

export async function updateLeadStatusAction(leadId: string, status: string) {
  await requireLeadManager();

  if (!VALID_STATUSES.includes(status as LeadStatus)) {
    throw new Error("Status inválido");
  }

  const leadStatus = status as LeadStatus;

  await prisma.$transaction(async (tx) => {
    const lead = await tx.lead.update({
      where: { id: leadId, ...NOT_DELETED },
      data: { status: leadStatus },
      select: { vehicleId: true },
    });

    if (leadStatus === "WON" && lead.vehicleId) {
      const vehicle = await tx.vehicle.findUnique({
        where: { id: lead.vehicleId },
        select: { status: true },
      });

      if (vehicle && (vehicle.status === "PUBLISHED" || vehicle.status === "RESERVED")) {
        await tx.vehicle.update({
          where: { id: lead.vehicleId },
          data: { status: "SOLD" },
        });
      }
    }
  });

  revalidatePath("/admin/crm");
  revalidatePath("/admin/leads");
  revalidatePath(`/admin/leads/${leadId}`);
  revalidatePath("/admin");
  revalidatePath("/admin/veiculos");
}

export async function batchUpdateLeadStatusAction(leadIds: string[], status: string) {
  await requireLeadManager();

  if (!VALID_STATUSES.includes(status as LeadStatus)) {
    throw new Error("Status inválido");
  }

  const leadStatus = status as LeadStatus;

  await prisma.lead.updateMany({
    where: { id: { in: leadIds }, ...NOT_DELETED },
    data: { status: leadStatus },
  });

  revalidatePath("/admin/crm");
  revalidatePath("/admin/leads");
  revalidatePath("/admin");
}

export async function updateLeadNoteAction(leadId: string, note: string) {
  await requireLeadManager();

  await prisma.lead.update({
    where: { id: leadId, ...NOT_DELETED },
    data: { internalNote: note || null },
  });

  revalidatePath(`/admin/leads/${leadId}`);
}

/** CRM dropdown assignment only. Must not set Conversation HUMAN_ACTIVE. */
export async function updateLeadAssignmentAction(leadId: string, assignedToUserId: string | null) {
  await requireLeadManager();

  if (assignedToUserId) {
    const user = await prisma.user.findFirst({
      where: { id: assignedToUserId, isActive: true },
      select: { id: true },
    });
    if (!user) {
      throw new Error("Vendedor inválido");
    }
  }

  await prisma.lead.update({
    where: { id: leadId, ...NOT_DELETED },
    data: { assignedToUserId: assignedToUserId || null },
  });

  revalidatePath(`/admin/leads/${leadId}`);
  revalidatePath("/admin/leads");
}

export async function createManualLeadAction(input: unknown) {
  await requireLeadManager();

  const parsed = createManualLeadSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false as const, error: parsed.error.flatten().fieldErrors };
  }

  const { name, phone, email, type, message, vehicleId, nameResolution } = parsed.data;

  if (vehicleId) {
    const vehicle = await prisma.vehicle.findUnique({
      where: { id: vehicleId },
      select: { id: true },
    });
    if (!vehicle) {
      return { ok: false as const, error: { vehicleId: ["Veículo não encontrado"] } };
    }
  }

  const customerResult = await resolveCustomerForLead(name, phone, email, nameResolution);
  if (!customerResult.ok) {
    return { ok: false as const, conflict: customerResult.conflict };
  }

  const lead = await prisma.lead.create({
    data: {
      type,
      status: "NEW",
      source: "UNKNOWN",
      channel: "MANUAL",
      name: customerResult.leadName,
      phone,
      email: email?.trim() || null,
      message: message?.trim() || null,
      vehicleId: vehicleId || null,
      customerId: customerResult.customerId || null,
    },
  });

  revalidatePath("/admin/leads");
  revalidatePath("/admin/crm");
  revalidatePath("/admin");
  revalidatePath("/admin/leads");

  return { ok: true as const, id: lead.id };
}

export async function deleteLeadAction(leadId: string) {
  try {
    await requireLeadManager();
  } catch (e) {
    return handleAuthError(e);
  }

  const lead = await prisma.lead.findFirst({
    where: { id: leadId, ...NOT_DELETED },
    select: { id: true },
  });
  if (!lead) {
    return { ok: false as const, error: "Lead não encontrado" };
  }

  await prisma.lead.update({
    where: { id: leadId },
    data: { deletedAt: new Date() },
  });

  revalidatePath("/admin/leads");
  revalidatePath("/admin/crm");
  revalidatePath("/admin");
  revalidatePath(`/admin/leads/${leadId}`);

  return { ok: true as const };
}

function blankToNull(value: string | null | undefined): string | null {
  const trimmed = value?.trim() ?? "";
  return trimmed ? trimmed : null;
}

function parseMoneyField(raw: string | undefined, label: string): { ok: true; value: number | null } | { ok: false; error: string } {
  const n = parseOptionalNumber(raw);
  if (isInvalidNumber(n) || (n != null && n < 0)) {
    return { ok: false, error: `${label} inválido` };
  }
  return { ok: true, value: n };
}

export async function updateLeadContactAction(input: unknown) {
  try {
    await requireLeadManager();
  } catch (e) {
    return handleAuthError(e);
  }

  const parsed = updateLeadContactSchema.safeParse(input);
  if (!parsed.success) {
    const firstError = Object.values(parsed.error.flatten().fieldErrors).flat()[0];
    return { ok: false as const, error: firstError ?? "Dados inválidos" };
  }

  const data = parsed.data;
  const lead = await prisma.lead.findFirst({
    where: { id: data.leadId, ...NOT_DELETED },
    select: {
      id: true,
      phone: true,
      whatsapp: true,
      customerId: true,
      financingRequest: { select: { id: true } },
    },
  });
  if (!lead) {
    return { ok: false as const, error: "Lead não encontrado" };
  }

  if (data.cpfTouched) {
    const digits = digitsOnly(data.cpf ?? "");
    if (digits && digits.length !== 11) {
      return { ok: false as const, error: "CPF inválido" };
    }
  }

  const customerResult = await resolveCustomerForLead(
    data.name,
    data.phone,
    data.email,
    data.nameResolution,
  );
  if (!customerResult.ok) {
    return { ok: false as const, conflict: customerResult.conflict };
  }

  const previousDigits = normalizePhone(lead.phone);
  const nextDigits = normalizePhone(data.phone);
  if (nextDigits.length < 10) {
    return { ok: false as const, error: "Telefone inválido" };
  }
  const whatsapp =
    !lead.whatsapp || normalizePhone(lead.whatsapp) === previousDigits ? nextDigits : lead.whatsapp;

  await prisma.$transaction(async (tx) => {
    await tx.lead.update({
      where: { id: lead.id },
      data: {
        name: customerResult.leadName,
        phone: nextDigits,
        whatsapp,
        email: blankToNull(data.email),
        city: blankToNull(data.city),
        state: blankToNull(data.state)?.toUpperCase() ?? null,
        customerId: customerResult.customerId || lead.customerId,
      },
    });

    if (lead.financingRequest) {
      const financingData: {
        cpf?: string | null;
        birthDate?: Date | null;
      } = {
        birthDate: parseDateInputValue(data.birthDate),
      };
      if (data.cpfTouched) {
        const digits = digitsOnly(data.cpf ?? "");
        financingData.cpf = digits ? formatCPF(digits) : null;
      }
      await tx.financingRequest.update({
        where: { leadId: lead.id },
        data: financingData,
      });
    }
  });

  revalidatePath(`/admin/leads/${lead.id}`);
  revalidatePath("/admin/leads");
  revalidatePath("/admin/crm");
  revalidatePath("/admin/clientes");
  if (customerResult.customerId) {
    revalidatePath(`/admin/clientes/${customerResult.customerId}`);
  }

  return { ok: true as const };
}

export async function updateLeadFinancingAction(input: unknown) {
  try {
    await requireLeadManager();
  } catch (e) {
    return handleAuthError(e);
  }

  const parsed = updateLeadFinancingSchema.safeParse(input);
  if (!parsed.success) {
    const firstError = Object.values(parsed.error.flatten().fieldErrors).flat()[0];
    return { ok: false as const, error: firstError ?? "Dados inválidos" };
  }

  const data = parsed.data;
  const lead = await prisma.lead.findFirst({
    where: { id: data.leadId, ...NOT_DELETED },
    select: { id: true, financingRequest: { select: { id: true } } },
  });
  if (!lead) {
    return { ok: false as const, error: "Lead não encontrado" };
  }
  if (!lead.financingRequest) {
    return { ok: false as const, error: "Este lead não tem ficha de financiamento" };
  }

  const income = parseMoneyField(data.monthlyIncome, "Renda mensal");
  if (!income.ok) return { ok: false as const, error: income.error };
  const down = parseMoneyField(data.downPayment, "Entrada");
  if (!down.ok) return { ok: false as const, error: down.error };

  const installments = parseOptionalInt(data.desiredInstallments, { min: 1, max: 84 });
  if (isInvalidNumber(installments)) {
    return { ok: false as const, error: "Prazo inválido" };
  }

  const license =
    data.hasDriverLicense === "true" ? true : data.hasDriverLicense === "false" ? false : null;

  await prisma.financingRequest.update({
    where: { leadId: lead.id },
    data: {
      monthlyIncome: income.value,
      downPayment: down.value,
      desiredInstallments: installments,
      hasDriverLicense: license,
      occupation: blankToNull(data.occupation),
      notes: blankToNull(data.notes),
    },
  });

  revalidatePath(`/admin/leads/${lead.id}`);
  revalidatePath("/admin/leads");
  return { ok: true as const };
}

export async function updateLeadSellAction(input: unknown) {
  try {
    await requireLeadManager();
  } catch (e) {
    return handleAuthError(e);
  }

  const parsed = updateLeadSellSchema.safeParse(input);
  if (!parsed.success) {
    const firstError = Object.values(parsed.error.flatten().fieldErrors).flat()[0];
    return { ok: false as const, error: firstError ?? "Dados inválidos" };
  }

  const data = parsed.data;
  const lead = await prisma.lead.findFirst({
    where: { id: data.leadId, ...NOT_DELETED },
    select: { id: true, sellRequest: { select: { id: true } } },
  });
  if (!lead) {
    return { ok: false as const, error: "Lead não encontrado" };
  }
  if (!lead.sellRequest) {
    return { ok: false as const, error: "Este lead não tem ficha de venda" };
  }

  const yearManufacture = parseOptionalInt(data.yearManufacture, { min: 1900, max: 2100 });
  const yearModel = parseOptionalInt(data.yearModel, { min: 1900, max: 2100 });
  const mileage = parseOptionalInt(data.mileage, { min: 0 });
  if (isInvalidNumber(yearManufacture) || isInvalidNumber(yearModel) || isInvalidNumber(mileage)) {
    return { ok: false as const, error: "Ano ou quilometragem inválidos" };
  }

  await prisma.sellRequest.update({
    where: { leadId: lead.id },
    data: {
      brand: blankToNull(data.brand),
      model: blankToNull(data.model),
      version: blankToNull(data.version),
      yearManufacture,
      yearModel,
      mileage,
      fuelType: blankToNull(data.fuelType),
      transmission: blankToNull(data.transmission),
      saleMode: data.saleMode ? data.saleMode : null,
      observations: blankToNull(data.observations),
    },
  });

  revalidatePath(`/admin/leads/${lead.id}`);
  revalidatePath("/admin/leads");
  return { ok: true as const };
}

export async function updateLeadVehicleInterestsAction(leadId: string, vehicleIds: string[]) {
  await requireLeadManager();

  const uniqueIds = Array.from(new Set(vehicleIds.filter(Boolean)));
  const lead = await prisma.lead.findFirst({
    where: { id: leadId, ...NOT_DELETED },
    select: {
      id: true,
      vehicleInterests: { select: { vehicleId: true, isPrimary: true } },
    },
  });
  if (!lead) {
    return { ok: false as const, error: "Lead não encontrado" };
  }

  if (uniqueIds.length > 0) {
    const found = await prisma.vehicle.findMany({
      where: { id: { in: uniqueIds } },
      select: { id: true },
    });
    if (found.length !== uniqueIds.length) {
      return { ok: false as const, error: "Um ou mais veículos não foram encontrados" };
    }
  }

  const currentPrimary =
    lead.vehicleInterests.find((item) => item.isPrimary)?.vehicleId ?? null;
  const primaryId = nextPrimaryVehicleId(uniqueIds, currentPrimary);

  await prisma.$transaction(async (tx) => {
    await tx.leadVehicleInterest.deleteMany({ where: { leadId } });
    if (uniqueIds.length > 0) {
      await tx.leadVehicleInterest.createMany({
        data: uniqueIds.map((vehicleId) => ({
          leadId,
          vehicleId,
          isPrimary: vehicleId === primaryId,
        })),
      });
    }
    await tx.lead.update({
      where: { id: leadId },
      data: { vehicleId: primaryId },
    });
  });

  revalidatePath(`/admin/leads/${leadId}`);
  revalidatePath("/admin/leads");
  return { ok: true as const };
}
