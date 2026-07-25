import "server-only";

import { redirect } from "next/navigation";
import type { UserRole } from "@prisma/client";
import {
  ForbiddenError,
  requireAdminSession,
  UnauthorizedError,
} from "./require-admin-session";
import {
  BRAND_READ_ROLES,
  BRAND_WRITE_ROLES,
  CONTENT_ROLES,
  CUSTOMER_READ_ROLES,
  CUSTOMER_WRITE_ROLES,
  FULL_ACCESS_ROLES,
  LEAD_ROLES,
  VEHICLE_WRITE_ROLES,
  canAccessSection,
  canWriteBrands,
  canWriteVehicles,
  getVisibleNavItems,
  getBottomNavPriority,
  resolveSectionFromPathname,
  type AdminSection,
  type NavItemKey,
} from "../rbac-config";

export {
  FULL_ACCESS_ROLES,
  LEAD_ROLES,
  CONTENT_ROLES,
  VEHICLE_READ_ROLES,
  VEHICLE_WRITE_ROLES,
  BRAND_WRITE_ROLES,
  BRAND_READ_ROLES,
  CUSTOMER_READ_ROLES,
  CUSTOMER_WRITE_ROLES,
  canAccessSection,
  canWriteVehicles,
  canWriteBrands,
  getVisibleNavItems,
  getBottomNavPriority,
  resolveSectionFromPathname,
  type AdminSection,
  type NavItemKey,
  NAV_ITEM_KEYS,
} from "../rbac-config";

export { ForbiddenError, UnauthorizedError };

/** Validates session + role membership. Throws UnauthorizedError or ForbiddenError. */
export async function requireAdminRole(allowedRoles: UserRole[]) {
  const ctx = await requireAdminSession();
  if (!allowedRoles.includes(ctx.user.role)) {
    throw new ForbiddenError();
  }
  return ctx;
}

/** Page guard: redirects to /admin?forbidden=1 when role lacks section access. */
export async function guardAdminSection(section: AdminSection) {
  const { user } = await requireAdminSession();
  if (!canAccessSection(user.role, section)) {
    redirect("/admin?forbidden=1");
  }
  return user;
}

/** Blocks vehicle write routes for read-only roles. */
export async function guardVehicleWrite() {
  const { user } = await requireAdminSession();
  if (!canWriteVehicles(user.role)) {
    redirect("/admin?forbidden=1");
  }
  return user;
}

/** Blocks brand write routes for read-only roles. */
export async function guardBrandWrite() {
  const { user } = await requireAdminSession();
  if (!canWriteBrands(user.role)) {
    redirect("/admin?forbidden=1");
  }
  return user;
}
