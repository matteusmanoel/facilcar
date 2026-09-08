"use server";

import { revalidatePath } from "next/cache";
import {
  ForbiddenError,
  LEAD_ROLES,
  UnauthorizedError,
  requireAdminRole,
} from "@/features/auth/server/rbac";
import { prisma } from "@/lib/db";
import { interpretClaimCount } from "./claim-result";

const NOT_DELETED = { deletedAt: null } as const;

function handleAuthError(e: unknown) {
  if (e instanceof UnauthorizedError) return { ok: false as const, error: e.message };
  if (e instanceof ForbiddenError) return { ok: false as const, error: e.message };
  throw e;
}

async function requireLeadManager() {
  return requireAdminRole(LEAD_ROLES);
}

function revalidateLead(leadId: string) {
  revalidatePath(`/admin/leads/${leadId}`);
  revalidatePath("/admin/leads");
  revalidatePath("/admin/crm");
  revalidatePath("/admin");
}

const CONVERSATION_SELECT = {
  id: true,
  botStatus: true,
  ownershipRevision: true,
  assumedByUserId: true,
  resumedByUserId: true,
} as const;

/**
 * Explicit Assumir. Owner is always the session user — extra client args are ignored.
 * Sets Conversation HUMAN_ACTIVE + ownershipRevision CAS. Assigns the lead.
 * Never mutates Lead.status.
 */
export async function claimLeadAction(leadId: string, _clientOwnerId?: unknown) {
  void _clientOwnerId;
  let userId: string;
  try {
    const { user } = await requireLeadManager();
    userId = user.id;
  } catch (e) {
    return handleAuthError(e);
  }

  const lead = await prisma.lead.findFirst({
    where: { id: leadId, ...NOT_DELETED },
    select: {
      id: true,
      assignedToUserId: true,
      conversation: { select: CONVERSATION_SELECT },
    },
  });
  if (!lead) {
    return { ok: false as const, error: "Lead não encontrado" };
  }

  const now = new Date();
  const interpreted = await prisma.$transaction(async (tx) => {
    const conversation = lead.conversation;

    if (conversation?.botStatus === "HUMAN_ACTIVE") {
      if (conversation.assumedByUserId === userId) {
        if (lead.assignedToUserId !== userId) {
          await tx.lead.update({
            where: { id: lead.id },
            data: { assignedToUserId: userId },
          });
        }
        return { ok: true as const };
      }
      return { ok: false as const, error: "already_claimed" as const };
    }

    if (conversation) {
      const cas = await tx.conversation.updateMany({
        where: {
          id: conversation.id,
          ownershipRevision: conversation.ownershipRevision,
          botStatus: { notIn: ["HUMAN_ACTIVE", "HUMAN_CLOSED"] },
        },
        data: {
          botStatus: "HUMAN_ACTIVE",
          assumedByUserId: userId,
          assumedAt: now,
          ownershipRevision: { increment: 1 },
        },
      });
      const claimed = interpretClaimCount(cas.count);
      if (!claimed.ok) {
        const latest = await tx.conversation.findUnique({
          where: { id: conversation.id },
          select: { botStatus: true, assumedByUserId: true },
        });
        if (latest?.botStatus === "HUMAN_ACTIVE" && latest.assumedByUserId === userId) {
          await tx.lead.update({
            where: { id: lead.id },
            data: { assignedToUserId: userId },
          });
          return { ok: true as const };
        }
        return claimed;
      }
      await tx.lead.update({
        where: { id: lead.id },
        data: { assignedToUserId: userId },
      });
      return { ok: true as const };
    }

    if (lead.assignedToUserId === userId) {
      return { ok: true as const };
    }
    const result = await tx.lead.updateMany({
      where: { id: lead.id, assignedToUserId: null, deletedAt: null },
      data: { assignedToUserId: userId },
    });
    return interpretClaimCount(result.count);
  });

  if (!interpreted.ok) return interpreted;

  revalidateLead(leadId);
  return { ok: true as const };
}

const DEFAULT_RESUME_REASON = "vendedor devolveu para a Júlia";

/**
 * Authorized resume: HUMAN_ACTIVE → AI_RESUMED.
 * Does not change Lead.status, assignedTo, juliaSummary, or history.
 * Does not send WhatsApp.
 */
export async function resumeConversationAction(leadId: string, reason?: string) {
  let userId: string;
  try {
    const { user } = await requireLeadManager();
    userId = user.id;
  } catch (e) {
    return handleAuthError(e);
  }

  const lead = await prisma.lead.findFirst({
    where: { id: leadId, ...NOT_DELETED },
    select: {
      id: true,
      conversation: { select: CONVERSATION_SELECT },
    },
  });
  if (!lead) {
    return { ok: false as const, error: "Lead não encontrado" };
  }
  if (!lead.conversation) {
    return { ok: false as const, error: "Conversa não encontrada" };
  }

  const conversation = lead.conversation;
  const resumeReason = reason?.trim() || DEFAULT_RESUME_REASON;
  const now = new Date();

  const interpreted = await prisma.$transaction(async (tx) => {
    if (conversation.botStatus === "AI_RESUMED" && conversation.resumedByUserId === userId) {
      return { ok: true as const };
    }

    const cas = await tx.conversation.updateMany({
      where: {
        id: conversation.id,
        ownershipRevision: conversation.ownershipRevision,
        botStatus: "HUMAN_ACTIVE",
      },
      data: {
        botStatus: "AI_RESUMED",
        resumedByUserId: userId,
        resumedAt: now,
        resumeReason,
        ownershipRevision: { increment: 1 },
      },
    });
    const claimed = interpretClaimCount(cas.count);
    if (!claimed.ok) {
      const latest = await tx.conversation.findUnique({
        where: { id: conversation.id },
        select: { botStatus: true, resumedByUserId: true },
      });
      if (latest?.botStatus === "AI_RESUMED" && latest.resumedByUserId === userId) {
        return { ok: true as const };
      }
      return claimed;
    }
    return { ok: true as const };
  });

  if (!interpreted.ok) return interpreted;

  revalidateLead(leadId);
  return { ok: true as const };
}
