"use client";

import { useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { toast } from "sonner";

export function ForbiddenToast() {
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    if (searchParams.get("forbidden") === "1") {
      toast.error("Você não tem permissão para acessar esta área.");
      router.replace("/admin");
    }
  }, [searchParams, router]);

  return null;
}
