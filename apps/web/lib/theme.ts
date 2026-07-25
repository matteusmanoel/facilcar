export type ThemeMode = "light" | "dark";

export const ADMIN_THEME_STORAGE_KEY = "facilcar-admin-theme";

export function normalizePublicTheme(value: string | null | undefined): ThemeMode {
  return value === "light" ? "light" : "dark";
}

export function isAdminThemeRoute(pathname: string | null | undefined): boolean {
  return Boolean(pathname?.startsWith("/admin"));
}

export const publicFormInputClass =
  "mt-1.5 w-full rounded-lg border border-facil-border bg-facil-card px-3 py-2.5 text-foreground shadow-sm transition placeholder:text-facil-muted focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/20 disabled:opacity-60";

export const publicFormLabelClass = "block text-sm font-medium text-foreground";

export const publicFormInputSimpleClass =
  "mt-1 w-full rounded border border-facil-border bg-facil-card px-3 py-2 text-foreground";
