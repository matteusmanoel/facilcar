import "server-only";

import { revalidatePath } from "next/cache";
import type { LeadSource, LeadType, Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { normalizePhone } from "@/features/customer/server/phone";

export type PublicFinancingDetails = {
  vehicleId?: string | null;
  cpf?: string | null;
  birthDate?: Date | null;
  hasDriverLicense?: boolean | null;
  monthlyIncome?: number | null;
  downPayment?: number | null;
  desiredInstallments?: number | null;
  vehicleYear?: number | null;
  vehicleModel?: string | null;
  notes?: string | null;
};

export type PublicSellDetails = {
  brand?: string | null;
  model?: string | null;
  version?: string | null;
  yearManufacture?: number | null;
  yearModel?: number | null;
  mileage?: number | null;
  fuelType?: string | null;
  transmission?: string | null;
  observations?: string | null;
  saleMode?: string | null;
  photoUrls?: string[];
};

export type PersistPublicFormLeadInput = {
  type: LeadType;
  source: LeadSource;
  name: string;
  phone: string;
  email?: string | null;
  message?: string | null;
  vehicleId?: string | null;
  metadata?: Prisma.InputJsonValue;
  financing?: PublicFinancingDetails | null;
  sell?: PublicSellDetails | null;
};

export type PersistPublicFormLeadResult = {
  leadId: string;
  customerId: string | null;
};

function emptyToNull(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

/** Single writer for public form intake: customer + lead + type details + admin signal. */
export async function persistPublicFormLead(
  input: PersistPublicFormLeadInput,
): Promise<PersistPublicFormLeadResult> {
  const phone = normalizePhone(input.phone);
  const name = input.name.trim();
  const email = emptyToNull(input.email ?? null);

  const result = await prisma.$transaction(async (tx) => {
    let vehicleId = emptyToNull(input.vehicleId ?? null);
    if (vehicleId) {
      const vehicle = await tx.vehicle.findUnique({
        where: { id: vehicleId },
        select: { id: true },
      });
      if (!vehicle) vehicleId = null;
    }

    const customer = phone
      ? await tx.customer.upsert({
          where: { phone },
          create: { name, phone, email },
          update: {
            name,
            ...(email ? { email } : {}),
          },
          select: { id: true },
        })
      : null;

    const lead = await tx.lead.create({
      data: {
        type: input.type,
        status: "NEW",
        source: input.source,
        channel: "FORM",
        name,
        phone: phone || input.phone,
        whatsapp: phone || null,
        email,
        message: emptyToNull(input.message ?? null),
        vehicleId,
        originUrl: null,
        customerId: customer?.id ?? null,
        metadataJson: input.metadata ?? undefined,
      },
      select: { id: true },
    });

    if (vehicleId) {
      await tx.leadVehicleInterest.create({
        data: { leadId: lead.id, vehicleId, isPrimary: true },
      });
    }

    if (input.financing) {
      const financing = input.financing;
      await tx.financingRequest.create({
        data: {
          leadId: lead.id,
          vehicleId: vehicleId ?? financing.vehicleId ?? null,
          cpf: emptyToNull(financing.cpf),
          birthDate: financing.birthDate ?? null,
          hasDriverLicense: financing.hasDriverLicense ?? null,
          monthlyIncome: financing.monthlyIncome ?? null,
          downPayment: financing.downPayment ?? null,
          desiredInstallments: financing.desiredInstallments ?? null,
          vehicleYear: financing.vehicleYear ?? null,
          vehicleModel: emptyToNull(financing.vehicleModel),
          notes: emptyToNull(financing.notes),
        },
      });
    }

    if (input.sell) {
      const sell = input.sell;
      await tx.sellRequest.create({
        data: {
          leadId: lead.id,
          brand: emptyToNull(sell.brand),
          model: emptyToNull(sell.model),
          version: emptyToNull(sell.version),
          yearManufacture: sell.yearManufacture ?? null,
          yearModel: sell.yearModel ?? null,
          mileage: sell.mileage ?? null,
          fuelType: emptyToNull(sell.fuelType),
          transmission: emptyToNull(sell.transmission),
          observations: emptyToNull(sell.observations),
          saleMode: emptyToNull(sell.saleMode),
          photoUrls: sell.photoUrls ?? [],
        },
      });
    }

    await tx.sdrNotification.create({
      data: {
        leadId: lead.id,
        type: "NEW_QUALIFIED",
      },
    });

    return { leadId: lead.id, customerId: customer?.id ?? null };
  });

  revalidatePath("/admin");
  revalidatePath("/admin/leads");
  revalidatePath("/admin/crm");
  revalidatePath("/admin/clientes");
  if (result.customerId) {
    revalidatePath(`/admin/clientes/${result.customerId}`);
  }
  revalidatePath(`/admin/leads/${result.leadId}`);

  return result;
}
