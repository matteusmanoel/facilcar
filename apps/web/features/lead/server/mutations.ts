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
import { createManualLeadSchema } from "@/schemas/lead";
import { prisma } from "@/lib/db";
import { interpretClaimCount } from "./claim-result";

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

/**
 * Atomic claim: only succeeds when lead is unassigned and not deleted.
 * First writer wins under concurrent Assumir clicks.
 */
export async function claimLeadAction(leadId: string) {
  let userId: string;
  try {
    const { user } = await requireLeadManager();
    userId = user.id;
  } catch (e) {
    return handleAuthError(e);
  }

  const result = await prisma.lead.updateMany({
    where: {
      id: leadId,
      assignedToUserId: null,
      deletedAt: null,
    },
    data: { assignedToUserId: userId },
  });

  const interpreted = interpretClaimCount(result.count);
  if (!interpreted.ok) return interpreted;

  revalidatePath(`/admin/leads/${leadId}`);
  revalidatePath("/admin/leads");
  revalidatePath("/admin/crm");
  revalidatePath("/admin");

  return { ok: true as const };
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
