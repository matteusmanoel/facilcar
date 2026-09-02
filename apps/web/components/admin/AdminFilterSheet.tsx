"use client";

import { useState } from "react";
import { ChevronDown, ListFilter } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/cn";

export function FilterFieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="mb-1.5 block text-xs font-medium text-facil-muted">{children}</label>;
}

export function FilterAccordion({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
      className="rounded-lg border border-facil-border bg-facil-surface/40"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-3 text-sm font-medium text-foreground [&::-webkit-details-marker]:hidden">
        <span>{title}</span>
        <ChevronDown
          className={cn("h-4 w-4 shrink-0 text-facil-muted transition", open && "rotate-180")}
        />
      </summary>
      <div className="space-y-4 border-t border-facil-border px-3 py-3">{children}</div>
    </details>
  );
}

type AdminFilterSheetProps = {
  activeCount: number;
  disabled?: boolean;
  onApply: () => void;
  onClear: () => void;
  children?: React.ReactNode;
  basicSection: React.ReactNode;
  advancedSection?: React.ReactNode;
  advancedDefaultOpen?: boolean;
};

export function AdminFilterSheet({
  activeCount,
  disabled,
  onApply,
  onClear,
  children,
  basicSection,
  advancedSection,
  advancedDefaultOpen,
}: AdminFilterSheetProps) {
  const [open, setOpen] = useState(false);

  function handleApply() {
    onApply();
    setOpen(false);
  }

  function handleClear() {
    onClear();
    setOpen(false);
  }

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="default"
        disabled={disabled}
        onClick={() => setOpen(true)}
        className="h-9 gap-2 border-facil-border bg-facil-card"
      >
        <ListFilter className="h-4 w-4" />
        Filtrar
        {activeCount > 0 ? (
          <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-facil-orange px-1.5 text-[11px] font-semibold text-white">
            {activeCount}
          </span>
        ) : null}
      </Button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Filtros</SheetTitle>
            <SheetDescription>Refine os resultados exibidos.</SheetDescription>
          </SheetHeader>
          <SheetBody className="space-y-6">
            <section className="space-y-4">
              <h3 className="text-sm font-semibold text-foreground">Filtros básicos</h3>
              {basicSection}
            </section>
            {advancedSection ? (
              <FilterAccordion title="Filtros avançados" defaultOpen={advancedDefaultOpen}>
                {advancedSection}
              </FilterAccordion>
            ) : null}
            {children}
          </SheetBody>
          <SheetFooter>
            <Button type="button" variant="ghost" onClick={handleClear} disabled={disabled}>
              Limpar
            </Button>
            <Button type="button" variant="primary" onClick={handleApply} disabled={disabled}>
              Aplicar filtros
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </>
  );
}
