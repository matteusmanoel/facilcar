import type { UserRole } from "@prisma/client";
import { FULL_ACCESS_ROLES } from "@/features/auth/rbac-config";

/** Original SDR documents (CNH, etc.) — SUPER_ADMIN / ADMIN only. LEAD_MANAGER → denied. */
export function canAccessSdrDocuments(role: UserRole): boolean {
  return (FULL_ACCESS_ROLES as readonly UserRole[]).includes(role);
}
