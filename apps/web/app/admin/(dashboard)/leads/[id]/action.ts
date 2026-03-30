"use server";

import { prisma } from "@/lib/db";
import type { LeadStatus } from "@prisma/client";

const VALID: LeadStatus[] = ["NEW", "IN_PROGRESS", "CONTACTED", "QUALIFIED", "WON", "LOST", "SPAM"];

export async function updateLeadStatusAction(leadId: string, status: string) {
  if (!VALID.includes(status as LeadStatus)) return;
  await prisma.lead.update({
    where: { id: leadId },
    data: { status: status as LeadStatus },
  });
}

export async function updateLeadNoteAction(leadId: string, note: string) {
  await prisma.lead.update({
    where: { id: leadId },
    data: { internalNote: note || null },
  });
}
