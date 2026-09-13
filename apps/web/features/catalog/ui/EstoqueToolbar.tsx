"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ListFilter, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FilterChips } from "@/components/ui/filter-chips";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PriceRangeFilter } from "@/features/catalog/ui/PriceRangeFilter";
import { RangeSliderField } from "@/features/catalog/ui/RangeSliderField";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { useDebounce } from "@/hooks/useDebounce";
import { cn } from "@/lib/cn";
import type { PriceBounds } from "@/features/catalog/lib/price-range";
import { BODY_STYLE_FILTERS } from "@/features/catalog/lib/public-catalog";

const ALL_BRANDS = "__all__";

const TYPES: { value: string; label: string }[] = [
  { value: "CAR", label: "Carro" },
  { value: "UTILITY", label: "Picape / utilitário" },
  { value: "MOTORCYCLE", label: "Moto" },
  { value: "OTHER", label: "Outro" },
];

const FUELS: { value: string; label: string }[] = [
  { value: "FLEX", label: "Flex" },
  { value: "GASOLINE", label: "Gasolina" },
  { value: "ETHANOL", label: "Etanol" },
  { value: "DIESEL", label: "Diesel" },
  { value: "ELECTRIC", label: "Elétrico" },
  { value: "HYBRID", label: "Híbrido" },
  { value: "OTHER", label: "Outro" },
];

const TRANS: { value: string; label: string }[] = [
  { value: "MANUAL", label: "Manual" },
  { value: "AUTOMATIC", label: "Automático" },
  { value: "AUTOMATED", label: "Automatizado" },
  { value: "CVT", label: "CVT" },
  { value: "OTHER", label: "Outro" },
];

const SORTS: { value: string; label: string }[] = [
  { value: "newest", label: "Mais recentes" },
  { value: "priceAsc", label: "Menor preço" },
  { value: "priceDesc", label: "Maior preço" },
  { value: "yearDesc", label: "Ano mais novo" },
  { value: "mileageAsc", label: "Menor km" },
];

type BrandOption = { id: string; name: string; slug: string };

type CurrentFilters = {
  q?: string;
  brand?: string;
  sort: string;
  type?: string;
  bodyStyle?: string;
  fuelType?: string;
  transmission?: string;
  priceMin?: number;
  priceMax?: number;
  yearMin?: number;
  yearMax?: number;
};

const EXTRA_KEYS = ["marca", "tipo", "carroceria", "combustivel", "cambio", "anoMin", "anoMax"] as const;

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="mb-1.5 block text-xs font-medium text-zinc-600 dark:text-zinc-400">{children}</label>;
}

export function EstoqueToolbar({
  brands,
  current,
  resultCount,
  priceBounds,
  yearBounds,
}: {
  brands: BrandOption[];
  current: CurrentFilters;
  resultCount: number;
  priceBounds: PriceBounds;
  yearBounds: PriceBounds;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const [q, setQ] = useState(current.q ?? "");
  const [priceMin, setPriceMin] = useState(current.priceMin != null ? String(current.priceMin) : "");
  const [priceMax, setPriceMax] = useState(current.priceMax != null ? String(current.priceMax) : "");
  const debouncedQ = useDebounce(q, 350);
  const debouncedMin = useDebounce(priceMin, 450);
  const debouncedMax = useDebounce(priceMax, 450);

  const [draftBrand, setDraftBrand] = useState(current.brand ?? "");
  const [draftType, setDraftType] = useState(current.type ?? "");
  const [draftBodyStyle, setDraftBodyStyle] = useState(current.bodyStyle ?? "");
  const [draftFuel, setDraftFuel] = useState(current.fuelType ?? "");
  const [draftTrans, setDraftTrans] = useState(current.transmission ?? "");
  const [draftYearMin, setDraftYearMin] = useState(current.yearMin != null ? String(current.yearMin) : "");
  const [draftYearMax, setDraftYearMax] = useState(current.yearMax != null ? String(current.yearMax) : "");

  useEffect(() => {
    setQ(current.q ?? "");
    setPriceMin(current.priceMin != null ? String(current.priceMin) : "");
    setPriceMax(current.priceMax != null ? String(current.priceMax) : "");
    setDraftBrand(current.brand ?? "");
    setDraftType(current.type ?? "");
    setDraftBodyStyle(current.bodyStyle ?? "");
    setDraftFuel(current.fuelType ?? "");
    setDraftTrans(current.transmission ?? "");
    setDraftYearMin(current.yearMin != null ? String(current.yearMin) : "");
    setDraftYearMax(current.yearMax != null ? String(current.yearMax) : "");
  }, [current]);

  const extraCount = useMemo(() => {
    return EXTRA_KEYS.reduce((n, key) => (searchParams.get(key) ? n + 1 : n), 0);
  }, [searchParams]);

  function commit(mutate: (sp: URLSearchParams) => void) {
    startTransition(() => {
      const sp = new URLSearchParams(searchParams.toString());
      mutate(sp);
      sp.delete("page");
      const qs = sp.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname);
      router.refresh();
    });
  }

  useEffect(() => {
    const next = debouncedQ.trim();
    const currentQ = searchParams.get("q") ?? "";
    if (next === currentQ) return;
    commit((sp) => {
      if (next) sp.set("q", next);
      else sp.delete("q");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- commit uses latest searchParams
  }, [debouncedQ]);

  useEffect(() => {
    const curMin = searchParams.get("precoMin") ?? "";
    const curMax = searchParams.get("precoMax") ?? "";
    if (debouncedMin === curMin && debouncedMax === curMax) return;
    commit((sp) => {
      if (debouncedMin.trim()) sp.set("precoMin", debouncedMin.trim());
      else sp.delete("precoMin");
      if (debouncedMax.trim()) sp.set("precoMax", debouncedMax.trim());
      else sp.delete("precoMax");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedMin, debouncedMax]);

  function applyExtraFilters() {
    commit((sp) => {
      const setOrDelete = (key: string, value: string) => {
        if (value) sp.set(key, value);
        else sp.delete(key);
      };
      setOrDelete("marca", draftBrand);
      setOrDelete("tipo", draftType);
      setOrDelete("carroceria", draftBodyStyle);
      setOrDelete("combustivel", draftFuel);
      setOrDelete("cambio", draftTrans);
      setOrDelete("anoMin", draftYearMin.trim());
      setOrDelete("anoMax", draftYearMax.trim());
    });
    setDrawerOpen(false);
  }

  function clearAll() {
    setQ("");
    setPriceMin("");
    setPriceMax("");
    setDraftBrand("");
    setDraftType("");
    setDraftBodyStyle("");
    setDraftFuel("");
    setDraftTrans("");
    setDraftYearMin("");
    setDraftYearMax("");
    startTransition(() => {
      router.push(pathname);
      router.refresh();
    });
    setDrawerOpen(false);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative w-full sm:min-w-[180px] sm:flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500 dark:text-zinc-400" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar modelo, marca…"
            className="h-10 w-full pl-9 pr-8"
            aria-label="Buscar veículos"
          />
          {q ? (
            <button
              type="button"
              onClick={() => setQ("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-foreground"
              aria-label="Limpar busca"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>

        <PriceRangeFilter
          bounds={priceBounds}
          min={priceMin}
          max={priceMax}
          onMinChange={setPriceMin}
          onMaxChange={setPriceMax}
        />

        <Select
          value={current.sort}
          onValueChange={(value) =>
            commit((sp) => {
              if (value && value !== "newest") sp.set("ordem", value);
              else sp.delete("ordem");
            })
          }
        >
          <SelectTrigger size="lg" className="w-full sm:w-[11.5rem] sm:shrink-0" aria-label="Ordenar">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORTS.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-10 w-full sm:w-auto"
          onClick={() => setDrawerOpen(true)}
        >
          <ListFilter className="h-4 w-4" />
          Filtros
          {extraCount > 0 ? (
            <span className="ml-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-facil-orange px-1.5 text-[11px] font-semibold text-white">
              {extraCount}
            </span>
          ) : null}
        </Button>
      </div>

      <FilterChips
        multiple={false}
        className="w-full"
        options={[...BODY_STYLE_FILTERS]}
        value={current.bodyStyle ?? ""}
        onChange={(value) =>
          commit((sp) => {
            if (value) sp.set("carroceria", value);
            else sp.delete("carroceria");
          })
        }
      />

      <p className={cn("text-xs font-medium text-zinc-600 dark:text-zinc-400", isPending && "opacity-60")}>
        {resultCount} veículo(s)
      </p>

      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Mais filtros</SheetTitle>
          </SheetHeader>
          <SheetBody className="space-y-5">
            <div>
              <FieldLabel>Marca</FieldLabel>
              <Select
                value={draftBrand || ALL_BRANDS}
                onValueChange={(value) => setDraftBrand(value === ALL_BRANDS ? "" : value)}
              >
                <SelectTrigger size="lg">
                  <SelectValue placeholder="Todas" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_BRANDS}>Todas</SelectItem>
                  {brands.map((b) => (
                    <SelectItem key={b.id} value={b.slug}>
                      {b.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <FieldLabel>Tipo</FieldLabel>
              <FilterChips multiple={false} options={TYPES} value={draftType} onChange={setDraftType} />
            </div>
            <div>
              <FieldLabel>Carroceria</FieldLabel>
              <FilterChips
                multiple={false}
                options={[...BODY_STYLE_FILTERS]}
                value={draftBodyStyle}
                onChange={setDraftBodyStyle}
              />
            </div>
            <div>
              <FieldLabel>Combustível</FieldLabel>
              <FilterChips multiple={false} options={FUELS} value={draftFuel} onChange={setDraftFuel} />
            </div>
            <div>
              <FieldLabel>Câmbio</FieldLabel>
              <FilterChips multiple={false} options={TRANS} value={draftTrans} onChange={setDraftTrans} />
            </div>
            <div>
              <FieldLabel>Ano</FieldLabel>
              <RangeSliderField
                bounds={yearBounds}
                min={draftYearMin}
                max={draftYearMax}
                onMinChange={setDraftYearMin}
                onMaxChange={setDraftYearMax}
                step={1}
                formatValue={(n) => String(n)}
                ariaLabel="Faixa de ano"
                thumbLabels={["Ano mínimo", "Ano máximo"]}
              />
            </div>
          </SheetBody>
          <SheetFooter>
            <Button type="button" variant="ghost" onClick={clearAll}>
              Limpar tudo
            </Button>
            <Button type="button" variant="primary" onClick={applyExtraFilters}>
              Aplicar
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}
