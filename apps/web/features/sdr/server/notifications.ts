import "server-only";

import { LEAD_ROLES, requireAdminRole } from "@/features/auth/server/rbac";
import { prisma } from "@/lib/db";

const NOTIFICATION_SELECT = {
  id: true,
  leadId: true,
  type: true,
  seenAt: true,
  createdAt: true,
  lead: { select: { id: true, name: true, temperature: true } },
} as const;

export type SdrNotificationRow = {
  id: string;
  leadId: string;
  type: string;
  seenAt: Date | null;
  createdAt: Date;
  lead: { id: string; name: string; temperature: string | null };
};

export async function listUnreadNotifications(limit = 50): Promise<SdrNotificationRow[]> {
  await requireAdminRole(LEAD_ROLES);

  return prisma.sdrNotification.findMany({
    where: { seenAt: null },
    orderBy: { createdAt: "desc" },
    take: Math.min(100, Math.max(1, limit)),
    select: NOTIFICATION_SELECT,
  });
}

export async function countUnreadNotifications(): Promise<number> {
  await requireAdminRole(LEAD_ROLES);

  return prisma.sdrNotification.count({
    where: { seenAt: null },
  });
}

export async function markNotificationsSeen(ids: string[]) {
  const { user } = await requireAdminRole(LEAD_ROLES);

  const uniqueIds = [...new Set(ids.filter(Boolean))];
  if (uniqueIds.length === 0) {
    return { ok: true as const, updated: 0 };
  }

  const result = await prisma.sdrNotification.updateMany({
    where: { id: { in: uniqueIds }, seenAt: null },
    data: {
      seenAt: new Date(),
      seenByUserId: user.id,
    },
  });

  return { ok: true as const, updated: result.count };
}
