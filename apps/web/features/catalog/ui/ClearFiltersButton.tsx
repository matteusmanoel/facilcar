"use client";

import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/cn";

type Props = {
  className?: string;
};

export function ClearFiltersButton({ className }: Props) {
  const router = useRouter();
  const pathname = usePathname();

  return (
    <button
      type="button"
      onClick={() => {
        router.push(pathname);
        router.refresh();
      }}
      className={cn(
        "inline-flex w-full items-center justify-center rounded-xl bg-facil-orange px-6 py-3 text-sm font-bold text-white shadow-md shadow-facil-orange/25 transition hover:bg-facil-orange-hover sm:w-auto",
        className,
      )}
    >
      Limpar filtros
    </button>
  );
}
