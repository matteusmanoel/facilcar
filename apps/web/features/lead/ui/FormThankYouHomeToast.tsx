"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { toast } from "sonner";
import { consumeFormThankYouToast } from "@/features/lead/lib/form-thank-you";

export function FormThankYouHomeToast() {
  const pathname = usePathname();

  useEffect(() => {
    if (pathname !== "/") return;
    const pending = consumeFormThankYouToast();
    if (!pending) return;
    toast.success(pending.title, {
      description: pending.description,
      duration: 6500,
    });
  }, [pathname]);

  return null;
}
