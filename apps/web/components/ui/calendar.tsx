"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker } from "react-day-picker";
import { ptBR } from "date-fns/locale";
import type { DateRange } from "react-day-picker";
import { cn } from "@/lib/cn";
import { buttonVariants } from "@/components/ui/button";

import "react-day-picker/style.css";

export type { DateRange };

type CalendarProps = React.ComponentProps<typeof DayPicker>;

function Calendar({ className, classNames, showOutsideDays = true, ...props }: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      locale={ptBR}
      className={cn("rdp-root p-3", className)}
      classNames={{
        root: "w-fit",
        months: "flex flex-col sm:flex-row gap-4",
        month: "flex flex-col gap-4",
        month_caption: "flex justify-center pt-1 relative items-center h-9 w-full px-9",
        caption_label: "text-sm font-medium",
        nav: "flex items-center gap-1",
        button_previous: cn(
          buttonVariants({ variant: "outline", size: "icon-sm" }),
          "absolute left-1 size-7 bg-transparent p-0 opacity-80 hover:opacity-100",
        ),
        button_next: cn(
          buttonVariants({ variant: "outline", size: "icon-sm" }),
          "absolute right-1 size-7 bg-transparent p-0 opacity-80 hover:opacity-100",
        ),
        month_grid: "w-full border-collapse",
        weekdays: "flex",
        weekday: "text-muted-foreground w-9 font-normal text-[0.8rem] text-center text-zinc-500",
        week: "flex w-full mt-2",
        day: "relative p-0 text-center text-sm focus-within:relative focus-within:z-20",
        day_button: cn(
          "size-9 p-0 font-normal rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800",
          "aria-selected:opacity-100",
        ),
        selected:
          "bg-facil-orange text-white hover:bg-facil-orange hover:text-white focus:bg-facil-orange [&>button]:bg-facil-orange [&>button]:text-white [&>button]:hover:bg-facil-orange",
        today: "bg-zinc-100 text-zinc-900 dark:bg-zinc-800",
        outside: "text-zinc-400 opacity-50",
        disabled: "text-zinc-300 opacity-50",
        range_middle:
          "aria-selected:bg-facil-orange-light dark:aria-selected:bg-zinc-800/80 rounded-none",
        range_start: "rounded-l-md",
        range_end: "rounded-r-md",
        hidden: "invisible",
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation, className: chClass, ...rest }) => {
          if (orientation === "left") {
            return <ChevronLeft className={cn("h-4 w-4", chClass)} {...rest} />;
          }
          return <ChevronRight className={cn("h-4 w-4", chClass)} {...rest} />;
        },
      }}
      {...props}
    />
  );
}
Calendar.displayName = "Calendar";

export { Calendar };
