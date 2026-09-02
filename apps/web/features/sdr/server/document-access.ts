import type { UserRole } from "@prisma/client";
import { FULL_ACCESS_ROLES, LEAD_ROLES } from "@/features/auth/rbac-config";

/** SDR + customer documents — CRM operators (LEAD_MANAGER included). */
export function canAccessSdrDocuments(role: UserRole): boolean {
  return (LEAD_ROLES as readonly UserRole[]).includes(role);
}

export function canAccessCustomerDocuments(role: UserRole): boolean {
  return (
    (LEAD_ROLES as readonly UserRole[]).includes(role) ||
    (FULL_ACCESS_ROLES as readonly UserRole[]).includes(role)
  );
}
