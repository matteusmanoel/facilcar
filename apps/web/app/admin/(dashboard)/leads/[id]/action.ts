"use server";

import { prisma } from "@/lib/db";
import type { $Enums } from "@prisma/client";

const VALID: $Enums.LeadStatus[] = ["NEW", "IN_PROGRESS", "CONTACTED", "QUALIFIED", "WON", "LOST", "SPAM"];

export async function updateLeadStatusAction(leadId: string, status: string) {
  if (!VALID.includes(status as $Enums.LeadStatus)) return;
  await prisma.lead.update({
    where: { id: leadId },
    data: { status: status as $Enums.LeadStatus },
  });
}
