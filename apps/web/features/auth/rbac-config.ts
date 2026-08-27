import type { UserRole } from "@prisma/client";

export const FULL_ACCESS_ROLES: UserRole[] = ["SUPER_ADMIN", "ADMIN"];
export const LEAD_ROLES: UserRole[] = ["SUPER_ADMIN", "ADMIN", "LEAD_MANAGER"];
export const CONTENT_ROLES: UserRole[] = ["SUPER_ADMIN", "ADMIN", "EDITOR"];
export const VEHICLE_READ_ROLES: UserRole[] = ["SUPER_ADMIN", "ADMIN", "LEAD_MANAGER"];
export const VEHICLE_WRITE_ROLES: UserRole[] = ["SUPER_ADMIN", "ADMIN"];
export const BRAND_WRITE_ROLES: UserRole[] = ["SUPER_ADMIN", "ADMIN"];
export const BRAND_READ_ROLES: UserRole[] = ["SUPER_ADMIN", "ADMIN", "EDITOR"];
export const CUSTOMER_READ_ROLES: UserRole[] = ["SUPER_ADMIN", "ADMIN", "LEAD_MANAGER"];
export const CUSTOMER_WRITE_ROLES: UserRole[] = ["SUPER_ADMIN", "ADMIN", "LEAD_MANAGER"];

export type AdminSection =
  | "dashboard"
  | "veiculos"
  | "leads"
  | "usuarios"
  | "paginas"
  | "blog"
  | "configuracoes";

export type NavItemKey =
  | "dashboard"
  | "veiculos"
  | "leads"
  | "usuarios"
  | "paginas"
  | "blog"
  | "configuracoes";

export const NAV_ITEM_KEYS: NavItemKey[] = [
  "dashboard",
  "veiculos",
  "leads",
  "usuarios",
  "paginas",
  "blog",
  "configuracoes",
];

const SECTION_ROLES: Record<AdminSection, UserRole[]> = {
  dashboard: ["SUPER_ADMIN", "ADMIN", "LEAD_MANAGER", "EDITOR"],
  veiculos: VEHICLE_READ_ROLES,
  leads: LEAD_ROLES,
  usuarios: FULL_ACCESS_ROLES,
  paginas: CONTENT_ROLES,
  blog: CONTENT_ROLES,
  configuracoes: CONTENT_ROLES,
};

export function canAccessSection(role: UserRole, section: AdminSection): boolean {
  return SECTION_ROLES[section].includes(role);
}

export function canWriteVehicles(role: UserRole): boolean {
  return VEHICLE_WRITE_ROLES.includes(role);
}

export function canWriteBrands(role: UserRole): boolean {
  return BRAND_WRITE_ROLES.includes(role);
}

export function getVisibleNavItems(role: UserRole): NavItemKey[] {
  return NAV_ITEM_KEYS.filter((key) => canAccessSection(role, key));
}

/** Mobile bottom nav: up to 5 items, prioritized per role. */
export function getBottomNavPriority(role: UserRole): NavItemKey[] {
  if (role === "EDITOR") {
    return ["dashboard", "blog", "paginas", "configuracoes"];
  }
  if (role === "LEAD_MANAGER") {
    return ["dashboard", "leads", "veiculos"];
  }
  return ["dashboard", "veiculos", "leads", "configuracoes"];
}

export function resolveSectionFromPathname(pathname: string): AdminSection | null {
  if (pathname === "/admin") return "dashboard";
  if (pathname.startsWith("/admin/veiculos")) return "veiculos";
  if (pathname.startsWith("/admin/leads") || pathname.startsWith("/admin/crm")) return "leads";
  if (pathname.startsWith("/admin/usuarios")) return "usuarios";
  if (pathname.startsWith("/admin/paginas")) return "paginas";
  if (pathname.startsWith("/admin/blog")) return "blog";
  if (pathname.startsWith("/admin/configuracoes")) return "configuracoes";
  return null;
}
