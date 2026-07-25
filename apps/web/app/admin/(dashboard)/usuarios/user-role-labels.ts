import type { UserRole } from "@prisma/client";

export const USER_ROLE_LABELS: Record<UserRole, string> = {
  SUPER_ADMIN: "Super admin",
  ADMIN: "Administrador",
  EDITOR: "Editor",
  LEAD_MANAGER: "Vendedor",
};

export const USER_ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: "LEAD_MANAGER", label: USER_ROLE_LABELS.LEAD_MANAGER },
  { value: "EDITOR", label: USER_ROLE_LABELS.EDITOR },
  { value: "ADMIN", label: USER_ROLE_LABELS.ADMIN },
  { value: "SUPER_ADMIN", label: USER_ROLE_LABELS.SUPER_ADMIN },
];

export function formatUserRole(role: string): string {
  return USER_ROLE_LABELS[role as UserRole] ?? role;
}
