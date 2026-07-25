"use client";

import { Toaster } from "sonner";

export function ThemedToaster() {
  return (
    <Toaster
      position="bottom-center"
      closeButton
      theme="dark"
      toastOptions={{
        classNames: {
          toast:
            "group toast !bg-facil-black !border-facil-border !text-white shadow-xl",
          title: "!text-white font-semibold",
          description: "!text-zinc-300",
          success: "!border-l-4 !border-l-facil-orange",
          error: "!border-l-4 !border-l-red-500",
          warning: "!border-l-4 !border-l-amber-500",
          info: "!border-l-4 !border-l-facil-orange",
          actionButton: "!bg-facil-orange !text-white",
          cancelButton: "!bg-facil-surface !text-foreground",
          closeButton:
            "!bg-facil-surface !border-facil-border !text-facil-muted hover:!text-white",
        },
      }}
    />
  );
}
