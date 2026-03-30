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
}: {
  from: Date | undefined;
  to: Date | undefined;
  onApply: (range: { from: Date | undefined; to: Date | undefined }) => void;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [range, setRange] = React.useState<DateRange | undefined>(() =>
    from && to ? { from, to } : from ? { from, to: undefined } : undefined,
  );
  const [currentMonth, setCurrentMonth] = React.useState<Date>(from ?? to ?? new Date());

  React.useEffect(() => {
    setRange(from && to ? { from, to } : from ? { from, to: undefined } : undefined);
  }, [from, to]);

  const label =
    from && to
      ? `${format(from, "dd/MM/yyyy", { locale: ptBR })} – ${format(to, "dd/MM/yyyy", { locale: ptBR })}`
      : from
        ? `${format(from, "dd/MM/yyyy", { locale: ptBR })} – …`
        : "Período";

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
        <div className="relative flex items-center justify-center border-b border-zinc-100 px-10 py-2.5 dark:border-zinc-800">
          <button
            type="button"
            onClick={() => setCurrentMonth((m) => subMonths(m, 1))}
            className="absolute left-2 flex h-7 w-7 items-center justify-center rounded-md border border-zinc-200 bg-white text-zinc-600 transition-colors hover:bg-zinc-50 hover:text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            {format(currentMonth, "MMMM yyyy", { locale: ptBR })}
            {" – "}
            {format(addMonths(currentMonth, 1), "MMMM yyyy", { locale: ptBR })}
          </span>
          <button
            type="button"
            onClick={() => setCurrentMonth((m) => addMonths(m, 1))}
            className="absolute right-2 flex h-7 w-7 items-center justify-center rounded-md border border-zinc-200 bg-white text-zinc-600 transition-colors hover:bg-zinc-50 hover:text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
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
          numberOfMonths={2}
          components={{ Nav: () => <span /> }}
        />

        <div className="flex justify-end gap-2 border-t border-zinc-100 p-3 dark:border-zinc-800">
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
