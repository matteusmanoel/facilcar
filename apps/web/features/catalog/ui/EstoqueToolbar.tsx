"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ListFilter, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  fuelType?: string;
  transmission?: string;
  priceMin?: number;
  priceMax?: number;
  yearMin?: number;
  yearMax?: number;
};

const EXTRA_KEYS = ["marca", "tipo", "combustivel", "cambio", "anoMin", "anoMax"] as const;

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="mb-1.5 block text-xs font-medium text-zinc-600 dark:text-zinc-400">{children}</label>;
}

function selectClass() {
  return "h-10 w-full rounded-lg border border-facil-border bg-facil-card px-3 text-sm text-foreground";
}

export function EstoqueToolbar({
  brands,
  current,
  resultCount,
  priceBounds,
}: {
  brands: BrandOption[];
  current: CurrentFilters;
  resultCount: number;
  priceBounds: { min: number; max: number };
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

  const hasAny =
    extraCount > 0 ||
    Boolean(current.q) ||
    current.priceMin != null ||
    current.priceMax != null ||
    current.sort !== "newest";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[180px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500 dark:text-zinc-400" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar modelo, marca…"
            className="h-10 pl-9 pr-8"
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

        <div className="flex h-10 items-center gap-1 rounded-lg border border-facil-border bg-facil-card px-2">
          <span className="px-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">R$</span>
          <input
            type="number"
            inputMode="numeric"
            min={0}
            placeholder={String(priceBounds.min)}
            value={priceMin}
            onChange={(e) => setPriceMin(e.target.value)}
            className="w-[5.5rem] bg-transparent py-1 text-sm text-foreground outline-none placeholder:text-zinc-400"
            aria-label="Preço mínimo"
          />
          <span className="text-zinc-400">–</span>
          <input
            type="number"
            inputMode="numeric"
            min={0}
            placeholder={String(priceBounds.max)}
            value={priceMax}
            onChange={(e) => setPriceMax(e.target.value)}
            className="w-[5.5rem] bg-transparent py-1 text-sm text-foreground outline-none placeholder:text-zinc-400"
            aria-label="Preço máximo"
          />
        </div>

        <select
          value={current.sort}
          onChange={(e) =>
            commit((sp) => {
              if (e.target.value && e.target.value !== "newest") sp.set("ordem", e.target.value);
              else sp.delete("ordem");
            })
          }
          className={cn(selectClass(), "w-auto min-w-[10rem]")}
          aria-label="Ordenar"
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>

        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-10"
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

        {hasAny ? (
          <Button type="button" variant="ghost" size="sm" className="h-10" onClick={clearAll}>
            Limpar
          </Button>
        ) : null}
      </div>

      <p className={cn("text-xs font-medium text-zinc-600 dark:text-zinc-400", isPending && "opacity-60")}>
        {resultCount} veículo(s)
      </p>

      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Mais filtros</SheetTitle>
          </SheetHeader>
          <SheetBody className="space-y-4">
            <div>
              <FieldLabel>Marca</FieldLabel>
              <select className={selectClass()} value={draftBrand} onChange={(e) => setDraftBrand(e.target.value)}>
                <option value="">Todas</option>
                {brands.map((b) => (
                  <option key={b.id} value={b.slug}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <FieldLabel>Tipo</FieldLabel>
              <select className={selectClass()} value={draftType} onChange={(e) => setDraftType(e.target.value)}>
                <option value="">Todos</option>
                {TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <FieldLabel>Combustível</FieldLabel>
              <select className={selectClass()} value={draftFuel} onChange={(e) => setDraftFuel(e.target.value)}>
                <option value="">Todos</option>
                {FUELS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <FieldLabel>Câmbio</FieldLabel>
              <select className={selectClass()} value={draftTrans} onChange={(e) => setDraftTrans(e.target.value)}>
                <option value="">Todos</option>
                {TRANS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <FieldLabel>Ano mín.</FieldLabel>
                <Input
                  type="number"
                  value={draftYearMin}
                  onChange={(e) => setDraftYearMin(e.target.value)}
                  placeholder="2015"
                />
              </div>
              <div>
                <FieldLabel>Ano máx.</FieldLabel>
                <Input
                  type="number"
                  value={draftYearMax}
                  onChange={(e) => setDraftYearMax(e.target.value)}
                  placeholder="2025"
                />
              </div>
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
