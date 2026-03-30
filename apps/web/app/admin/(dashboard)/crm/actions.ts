"use server";

import { prisma } from "@/lib/db";
import { revalidatePath } from "next/cache";
import type { LeadStatus } from "@prisma/client";

const VALID_STATUSES: LeadStatus[] = [
  "NEW",
  "IN_PROGRESS",
  "CONTACTED",
  "QUALIFIED",
  "WON",
  "LOST",
  "SPAM",
];

export async function updateLeadStatusAction(leadId: string, status: string) {
  if (!VALID_STATUSES.includes(status as LeadStatus)) {
    throw new Error("Status inválido");
  }

  await prisma.lead.update({
    where: { id: leadId },
    data: { status: status as LeadStatus },
  });

  revalidatePath("/admin/crm");
  revalidatePath("/admin/leads");
  revalidatePath("/admin");
}
