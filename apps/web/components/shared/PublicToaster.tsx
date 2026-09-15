"use client";

import { useTheme } from "next-themes";
import { Toaster } from "sonner";

export function PublicToaster() {
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme === "light" ? "light" : "dark";

  return (
    <Toaster
      position="bottom-right"
      closeButton
      theme={theme}
      offset={{
        bottom: "calc(1.25rem + var(--cookie-banner-offset, 0px))",
        right: 16,
      }}
      toastOptions={{
        classNames: {
          toast:
            "group toast !bg-facil-card !border-facil-border !text-foreground shadow-xl",
          title: "!text-foreground font-semibold",
          description: "!text-facil-muted",
          success: "!border-l-4 !border-l-facil-orange",
          error: "!border-l-4 !border-l-red-500",
          closeButton:
            "!bg-facil-surface !border-facil-border !text-facil-muted hover:!text-foreground",
        },
      }}
    />
  );
}
