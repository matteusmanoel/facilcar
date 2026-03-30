"use client";

import * as React from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export type BrandOption = { id: string; name: string; slug: string };

export function VehicleBrandCombobox({
  brands,
  value,
  onChange,
  error,
  label,
  required,
}: {
  brands: BrandOption[];
  value: string;
  onChange: (brandId: string) => void;
  error?: string;
  label: string;
  required?: boolean;
}) {
  const [open, setOpen] = React.useState(false);
  const selected = brands.find((b) => b.id === value);

  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        {label}
        {required && <span className="ml-0.5 text-facil-orange">*</span>}
      </label>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className={cn(
              "w-full justify-between font-normal h-9 px-3",
              !selected && "text-zinc-500",
              error && "border-red-400",
            )}
          >
            {selected ? selected.name : "Selecione a marca…"}
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
          <Command>
            <CommandInput placeholder="Buscar marca…" />
            <CommandList>
              <CommandEmpty>Nenhuma marca encontrada.</CommandEmpty>
              <CommandGroup>
                {brands.map((b) => (
                  <CommandItem
                    key={b.id}
                    value={`${b.name} ${b.slug}`}
                    onSelect={() => {
                      onChange(b.id);
                      setOpen(false);
                    }}
                  >
                    <Check className={cn("mr-2 h-4 w-4", value === b.id ? "opacity-100" : "opacity-0")} />
                    {b.name}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  );
}
