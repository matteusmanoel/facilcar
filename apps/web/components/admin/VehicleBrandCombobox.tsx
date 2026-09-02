"use client";

import * as React from "react";
import { Check, ChevronsUpDown, Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
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
import {
  createBrandInlineAction,
  deleteBrandInlineAction,
} from "@/features/admin/server/brands";

export type BrandOption = {
  id: string;
  name: string;
  slug: string;
  vehicleCount?: number;
};

export function VehicleBrandCombobox({
  brands: initialBrands,
  value,
  onChange,
  error,
  label,
  required,
  canManage = false,
}: {
  brands: BrandOption[];
  value: string;
  onChange: (brandId: string) => void;
  error?: string;
  label: string;
  required?: boolean;
  canManage?: boolean;
}) {
  const [open, setOpen] = React.useState(false);
  const [brands, setBrands] = React.useState(initialBrands);
  const [search, setSearch] = React.useState("");
  const [pending, setPending] = React.useState(false);

  React.useEffect(() => {
    setBrands(initialBrands);
  }, [initialBrands]);

  const selected = brands.find((b) => b.id === value);
  const trimmedSearch = search.trim();
  const exactMatch = brands.some(
    (b) => b.name.toLowerCase() === trimmedSearch.toLowerCase(),
  );
  const canCreate =
    canManage && trimmedSearch.length > 0 && !exactMatch && !pending;

  async function handleCreate() {
    if (!canCreate) return;
    setPending(true);
    try {
      const result = await createBrandInlineAction({ name: trimmedSearch });
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      setBrands((prev) => {
        if (prev.some((b) => b.id === result.brand.id)) return prev;
        return [...prev, result.brand].sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
      });
      onChange(result.brand.id);
      setSearch("");
      setOpen(false);
      toast.success(
        result.alreadyExisted ? "Marca já existia e foi selecionada." : "Marca criada.",
      );
    } finally {
      setPending(false);
    }
  }

  async function handleDelete(brand: BrandOption, e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!canManage || (brand.vehicleCount ?? 0) > 0 || pending) return;
    setPending(true);
    try {
      const result = await deleteBrandInlineAction(brand.id);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      setBrands((prev) => prev.filter((b) => b.id !== brand.id));
      if (value === brand.id) onChange("");
      toast.success("Marca removida.");
    } finally {
      setPending(false);
    }
  }

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
          <Command shouldFilter>
            <CommandInput
              placeholder="Buscar ou criar marca…"
              value={search}
              onValueChange={setSearch}
            />
            <CommandList>
              <CommandEmpty>
                {canManage ? "Digite o nome para criar uma marca." : "Nenhuma marca encontrada."}
              </CommandEmpty>
              {canCreate ? (
                <CommandGroup>
                  <CommandItem
                    value={`__create__${trimmedSearch}`}
                    onSelect={() => void handleCreate()}
                    disabled={pending}
                    className="gap-2 text-facil-orange"
                  >
                    {pending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Plus className="h-4 w-4" />
                    )}
                    Criar “{trimmedSearch}”
                  </CommandItem>
                </CommandGroup>
              ) : null}
              <CommandGroup>
                {brands.map((b) => {
                  const unused = (b.vehicleCount ?? 0) === 0;
                  return (
                    <CommandItem
                      key={b.id}
                      value={`${b.name} ${b.slug}`}
                      onSelect={() => {
                        onChange(b.id);
                        setOpen(false);
                        setSearch("");
                      }}
                      className="group"
                    >
                      <Check
                        className={cn(
                          "mr-2 h-4 w-4 shrink-0",
                          value === b.id ? "opacity-100" : "opacity-0",
                        )}
                      />
                      <span className="min-w-0 flex-1 truncate">{b.name}</span>
                      {canManage && unused ? (
                        <button
                          type="button"
                          aria-label={`Excluir marca ${b.name}`}
                          className="ml-2 rounded p-1 text-facil-muted opacity-0 transition hover:bg-red-50 hover:text-red-600 group-data-[selected=true]:opacity-100 group-hover:opacity-100 dark:hover:bg-red-950/40"
                          onClick={(e) => void handleDelete(b, e)}
                          disabled={pending}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      ) : null}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  );
}
