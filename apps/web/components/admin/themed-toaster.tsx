"use client";

import { useTheme } from "next-themes";
import { Toaster } from "sonner";

export function ThemedToaster() {
  const { resolvedTheme } = useTheme();
  const theme = resolvedTheme === "light" ? "light" : "dark";

  return (
    <Toaster
      position="bottom-center"
      closeButton
      theme={theme}
      toastOptions={{
        classNames: {
          toast:
            "group toast !bg-facil-card !border-facil-border !text-foreground shadow-xl",
          title: "!text-foreground font-semibold",
          description: "!text-facil-muted",
          success: "!border-l-4 !border-l-facil-orange",
          error: "!border-l-4 !border-l-red-500",
          warning: "!border-l-4 !border-l-amber-500",
          info: "!border-l-4 !border-l-facil-orange",
          actionButton: "!bg-facil-orange !text-white",
          cancelButton: "!bg-facil-surface !text-foreground",
          closeButton:
            "!bg-facil-surface !border-facil-border !text-facil-muted hover:!text-foreground",
        },
      }}
    />
  );
}
