"use client";

import * as React from "react";
import { format, addMonths, subMonths } from "date-fns";
import { ptBR } from "date-fns/locale";
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from "lucide-react";
import type { DateRange } from "react-day-picker";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export function DateRangePicker({
  from,
  to,
  onApply,
  disabled,
  className,
  open: controlledOpen,
  onOpenChange,
}: {
  from: Date | undefined;
  to: Date | undefined;
  onApply: (range: { from: Date | undefined; to: Date | undefined }) => void;
  disabled?: boolean;
  className?: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [internalOpen, setInternalOpen] = React.useState(false);
  const open = controlledOpen ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;
  const [range, setRange] = React.useState<DateRange | undefined>(() =>
    from && to ? { from, to } : from ? { from, to: undefined } : undefined,
  );
  const [currentMonth, setCurrentMonth] = React.useState<Date>(from ?? to ?? new Date());
  const [monthsToShow, setMonthsToShow] = React.useState(2);

  React.useEffect(() => {
    const media = window.matchMedia("(max-width: 639px)");
    const update = () => setMonthsToShow(media.matches ? 1 : 2);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  React.useEffect(() => {
    setRange(from && to ? { from, to } : from ? { from, to: undefined } : undefined);
    if (from) setCurrentMonth(from);
  }, [from?.getTime(), to?.getTime()]);

  const label =
    from && to
      ? `${format(from, "dd/MM/yyyy", { locale: ptBR })} – ${format(to, "dd/MM/yyyy", { locale: ptBR })}`
      : from
        ? `${format(from, "dd/MM/yyyy", { locale: ptBR })} – …`
        : "Intervalo personalizado";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          className={cn("justify-start gap-2 font-normal", className)}
        >
          <CalendarIcon className="h-4 w-4 shrink-0" />
          <span className="truncate">{label}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        {/* Navigation header with chevrons at the top corners */}
        <div className="relative flex items-center justify-center border-b border-facil-border px-10 py-2.5">
          <button
            type="button"
            onClick={() => setCurrentMonth((m) => subMonths(m, 1))}
            className="absolute left-2 flex h-7 w-7 items-center justify-center rounded-md border border-facil-border bg-facil-card text-foreground transition-colors hover:bg-facil-surface"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm font-medium text-foreground">
            {format(currentMonth, "MMMM yyyy", { locale: ptBR })}
            {monthsToShow > 1 && (
              <>
                {" – "}
                {format(addMonths(currentMonth, 1), "MMMM yyyy", { locale: ptBR })}
              </>
            )}
          </span>
          <button
            type="button"
            onClick={() => setCurrentMonth((m) => addMonths(m, 1))}
            className="absolute right-2 flex h-7 w-7 items-center justify-center rounded-md border border-facil-border bg-facil-card text-foreground transition-colors hover:bg-facil-surface"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        {/* Calendar without built-in navigation */}
        <Calendar
          mode="range"
          month={currentMonth}
          onMonthChange={setCurrentMonth}
          selected={range}
          onSelect={setRange}
          numberOfMonths={monthsToShow}
          components={{ Nav: () => <span /> }}
        />

        <div className="flex justify-end gap-2 border-t border-facil-border p-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setRange(undefined);
              onApply({ from: undefined, to: undefined });
              setOpen(false);
            }}
          >
            Limpar
          </Button>
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={() => {
              onApply({ from: range?.from, to: range?.to });
              setOpen(false);
            }}
          >
            Aplicar
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
