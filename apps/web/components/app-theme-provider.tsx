"use client";

import { usePathname } from "next/navigation";
import { ThemeProvider } from "@/components/theme-provider";
import {
  ADMIN_THEME_STORAGE_KEY,
  isAdminThemeRoute,
  type ThemeMode,
} from "@/lib/theme";

type AppThemeProviderProps = {
  publicTheme: ThemeMode;
  children: React.ReactNode;
};

export function AppThemeProvider({ publicTheme, children }: AppThemeProviderProps) {
  const pathname = usePathname();
  const adminRoute = isAdminThemeRoute(pathname);

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      forcedTheme={adminRoute ? undefined : publicTheme}
      storageKey={ADMIN_THEME_STORAGE_KEY}
      disableTransitionOnChange
      enableColorScheme
    >
      {children}
    </ThemeProvider>
  );
}
