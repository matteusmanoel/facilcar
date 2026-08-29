"use client";

import Link from "next/link";
import { Printer } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/cn";

type Props = {
  closeHref: string;
  closeLabel?: string;
  showPrint?: boolean;
};

export function PrintToolbar({ closeHref, closeLabel = "Fechar", showPrint = true }: Props) {
  return (
    <div className="print:hidden sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-zinc-200 bg-white px-4 py-3">
      <p className="text-sm text-zinc-600">
        {showPrint ? "Pré-visualização para impressão" : "Impressão"}
      </p>
      <div className="flex items-center gap-2">
        {showPrint ? (
          <Button type="button" variant="primary" size="sm" onClick={() => window.print()}>
            <Printer className="h-4 w-4" />
            Imprimir
          </Button>
        ) : null}
        <Link href={closeHref} className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
          {closeLabel}
        </Link>
      </div>
    </div>
  );
}
