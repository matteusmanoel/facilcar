"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react";
import type { MouseEvent } from "react";
import Link from "next/link";
import type { FuelType, Transmission, VehicleStatus, VehicleType } from "@prisma/client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ChevronDown, ExternalLink, MoreHorizontal, Search, X } from "lucide-react";
import { toast } from "sonner";
import { quickUpdateVehicleStatusAction } from "@/features/vehicle/server/mutations";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { AdminFilterSheet, FilterFieldLabel } from "@/components/admin/AdminFilterSheet";
import { ArchiveVehicleButton } from "./ArchiveVehicleButton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MultiSelect } from "@/components/ui/multi-select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useDebounce } from "@/hooks/useDebounce";
import { useClearSelectionOnEscape } from "@/hooks/useClearSelectionOnEscape";
import { serializeCsvParam } from "@/lib/query-filters";
import { cn } from "@/lib/cn";
import { rangeIds, toggleId, unionIds } from "@/lib/range-select";

type VehicleRow = {
  id: string;
  slug: string;
  title: string;
  status: string;
  priceCash: number | null;
  brand: { name: string };
  images: { url: string }[];
};

type BrandOption = { id: string; name: string; slug: string };

type VehicleListFilters = {
  statuses?: VehicleStatus[];
  brandIds?: string[];
  types?: VehicleType[];
  featuredValues?: boolean[];
  fuelTypes?: FuelType[];
  transmissions?: Transmission[];
  priceMin?: number;
  priceMax?: number;
  yearMin?: number;
  yearMax?: number;
};

const STATUS_OPTIONS: { value: VehicleStatus; label: string }[] = [
  { value: "DRAFT", label: "Rascunho" },
  { value: "PUBLISHED", label: "Publicado" },
  { value: "RESERVED", label: "Reservado" },
  { value: "SOLD", label: "Vendido" },
  { value: "ARCHIVED", label: "Arquivado" },
];

const TYPE_OPTIONS: { value: VehicleType; label: string }[] = [
  { value: "CAR", label: "Carro" },
  { value: "MOTORCYCLE", label: "Moto" },
  { value: "UTILITY", label: "Utilitário" },
  { value: "OTHER", label: "Outro" },
];

const FUEL_OPTIONS: { value: FuelType; label: string }[] = [
  { value: "GASOLINE", label: "Gasolina" },
  { value: "ETHANOL", label: "Etanol" },
  { value: "FLEX", label: "Flex" },
  { value: "DIESEL", label: "Diesel" },
  { value: "ELECTRIC", label: "Elétrico" },
  { value: "HYBRID", label: "Híbrido" },
  { value: "OTHER", label: "Outro" },
];

const TRANSMISSION_OPTIONS: { value: Transmission; label: string }[] = [
  { value: "MANUAL", label: "Manual" },
  { value: "AUTOMATIC", label: "Automático" },
  { value: "AUTOMATED", label: "Automatizado" },
  { value: "CVT", label: "CVT" },
  { value: "OTHER", label: "Outro" },
];

const QUICK_STATUS_OPTIONS = STATUS_OPTIONS;

const FEATURED_OPTIONS = [
  { value: "true", label: "Em destaque" },
  { value: "false", label: "Sem destaque" },
];

type DraftFilters = {
  statuses: string[];
  brandIds: string[];
  types: string[];
  featured: string[];
  fuelTypes: string[];
  transmissions: string[];
  priceMin: string;
  priceMax: string;
  yearMin: string;
  yearMax: string;
};

function filtersToDraft(filters: VehicleListFilters): DraftFilters {
  return {
    statuses: filters.statuses ?? [],
    brandIds: filters.brandIds ?? [],
    types: filters.types ?? [],
    featured: (filters.featuredValues ?? []).map((v) => (v ? "true" : "false")),
    fuelTypes: filters.fuelTypes ?? [],
    transmissions: filters.transmissions ?? [],
    priceMin: filters.priceMin != null ? String(filters.priceMin) : "",
    priceMax: filters.priceMax != null ? String(filters.priceMax) : "",
    yearMin: filters.yearMin != null ? String(filters.yearMin) : "",
    yearMax: filters.yearMax != null ? String(filters.yearMax) : "",
  };
}

function countActiveFilters(filters: VehicleListFilters): number {
  let n = 0;
  if (filters.statuses?.length) n++;
  if (filters.brandIds?.length) n++;
  if (filters.types?.length) n++;
  if (filters.featuredValues?.length) n++;
  if (filters.fuelTypes?.length) n++;
  if (filters.transmissions?.length) n++;
  if (filters.priceMin != null) n++;
  if (filters.priceMax != null) n++;
  if (filters.yearMin != null) n++;
  if (filters.yearMax != null) n++;
  return n;
}

interface VehiclesClientProps {
  vehicles: VehicleRow[];
  totalCount: number;
  page: number;
  pageSize: number;
  brands: BrandOption[];
  filters: VehicleListFilters;
  initialSearch: string;
  canWrite?: boolean;
}

function VehicleActionsMenu({
  vehicle,
  canWrite,
}: {
  vehicle: VehicleRow;
  canWrite: boolean;
}) {
  const [archiveOpen, setArchiveOpen] = useState(false);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 text-facil-muted hover:text-foreground"
            aria-label="Ações do veículo"
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <Link href={`/admin/veiculos/${vehicle.id}`} className="cursor-pointer">
              {canWrite ? "Editar" : "Ver detalhes"}
            </Link>
          </DropdownMenuItem>
          {canWrite && vehicle.status !== "ARCHIVED" ? (
            <DropdownMenuItem
              className="cursor-pointer"
              onClick={() => setArchiveOpen(true)}
            >
              Arquivar
            </DropdownMenuItem>
          ) : null}
          {vehicle.status === "PUBLISHED" ? (
            <DropdownMenuItem asChild>
              <Link
                href={`/estoque/${vehicle.slug}`}
                target="_blank"
                className="flex cursor-pointer items-center gap-1.5"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Ver no site
              </Link>
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem disabled className="text-facil-muted">
              Ver no site (não publicado)
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      {canWrite && vehicle.status !== "ARCHIVED" ? (
        <ArchiveVehicleButton
          vehicleId={vehicle.id}
          vehicleTitle={vehicle.title}
          currentStatus={vehicle.status}
          variant="menu"
          open={archiveOpen}
          onOpenChange={setArchiveOpen}
        />
      ) : null}
    </>
  );
}

function QuickStatusMenu({ vehicleId, currentStatus }: { vehicleId: string; currentStatus: string }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function handleStatusChange(status: VehicleStatus) {
    if (status === currentStatus) return;
    startTransition(async () => {
      try {
        await quickUpdateVehicleStatusAction(vehicleId, status);
        router.refresh();
        const label = QUICK_STATUS_OPTIONS.find((s) => s.value === status)?.label ?? status;
        toast.success(`Status atualizado: ${label}`);
      } catch {
        toast.error("Erro ao atualizar status. Tente novamente.");
      }
    });
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={isPending}
          className="h-7 gap-1 px-2 text-xs"
        >
          Status
          <ChevronDown className="h-3 w-3" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel className="text-xs">Alterar status</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {QUICK_STATUS_OPTIONS.map((option) => (
          <DropdownMenuItem
            key={option.value}
            disabled={option.value === currentStatus || isPending}
            onClick={() => handleStatusChange(option.value)}
            className="text-sm"
          >
            {option.label}
            {option.value === currentStatus ? " ✓" : ""}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function VehiclesClient({
  vehicles,
  totalCount,
  page,
  pageSize,
  brands,
  filters,
  initialSearch,
  canWrite = true,
}: VehiclesClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [search, setSearch] = useState(initialSearch);
  const debouncedSearch = useDebounce(search, 350);
  const [draft, setDraft] = useState<DraftFilters>(() => filtersToDraft(filters));
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const anchorIdRef = useRef<string | null>(null);
  const clearSelection = useCallback(() => setSelectedIds(new Set()), []);
  useClearSelectionOnEscape(clearSelection, selectedIds.size > 0);

  const activeFilterCount = useMemo(() => countActiveFilters(filters), [filters]);
  const hasAdvancedFilters =
    (filters.featuredValues?.length ?? 0) > 0 ||
    (filters.fuelTypes?.length ?? 0) > 0 ||
    (filters.transmissions?.length ?? 0) > 0 ||
    filters.priceMin != null ||
    filters.priceMax != null ||
    filters.yearMin != null ||
    filters.yearMax != null;

  useEffect(() => {
    setSearch(initialSearch);
  }, [initialSearch]);

  useEffect(() => {
    setDraft(filtersToDraft(filters));
  }, [filters]);

  useEffect(() => {
    const currentQ = searchParams.get("q") ?? "";
    if (debouncedSearch === currentQ) return;
    startTransition(() => {
      const sp = new URLSearchParams(searchParams.toString());
      if (debouncedSearch.trim()) sp.set("q", debouncedSearch.trim());
      else sp.delete("q");
      sp.set("page", "1");
      router.replace(`${pathname}?${sp.toString()}`);
      router.refresh();
    });
  }, [debouncedSearch, pathname, router, searchParams]);

  const pushSearchParams = useCallback(
    (mutate: (sp: URLSearchParams) => void) => {
      startTransition(() => {
        const sp = new URLSearchParams(searchParams.toString());
        mutate(sp);
        const qs = sp.toString();
        router.push(qs ? `${pathname}?${qs}` : pathname);
        router.refresh();
      });
    },
    [pathname, router, searchParams],
  );

  function applyFilter(updates: Record<string, string | undefined>) {
    pushSearchParams((sp) => {
      Object.entries(updates).forEach(([k, v]) => {
        if (v === undefined || v === "" || v === "all") sp.delete(k);
        else sp.set(k, v);
      });
      if (!Object.prototype.hasOwnProperty.call(updates, "page")) {
        sp.set("page", "1");
      }
    });
  }

  function applyDraftFilters() {
    pushSearchParams((sp) => {
      const setCsv = (key: string, values: string[]) => {
        const serialized = serializeCsvParam(values);
        if (serialized) sp.set(key, serialized);
        else sp.delete(key);
      };

      setCsv("status", draft.statuses);
      setCsv("brandId", draft.brandIds);
      setCsv("type", draft.types);
      setCsv("featured", draft.featured);
      setCsv("fuelType", draft.fuelTypes);
      setCsv("transmission", draft.transmissions);

      ["priceMin", "priceMax", "yearMin", "yearMax"].forEach((key) => {
        const value = draft[key as keyof DraftFilters] as string;
        if (value?.trim()) sp.set(key, value.trim());
        else sp.delete(key);
      });

      sp.set("page", "1");
    });
  }

  function clearFilters() {
    startTransition(() => {
      const sp = new URLSearchParams();
      const q = search.trim();
      if (q) sp.set("q", q);
      const qs = sp.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname);
      setDraft(filtersToDraft({}));
      router.refresh();
    });
  }

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const qActive = (searchParams.get("q") ?? "").trim();
  const hasActiveFilters = activeFilterCount > 0 || !!qActive;
  const vehicleIds = vehicles.map((v) => v.id);

  function handleRowClick(vehicle: VehicleRow, event: MouseEvent) {
    if (event.shiftKey || event.metaKey || event.ctrlKey) {
      event.preventDefault();
      if (event.shiftKey) {
        const range = rangeIds(vehicleIds, anchorIdRef.current, vehicle.id);
        setSelectedIds((prev) => unionIds(prev, range));
      } else {
        setSelectedIds((prev) => toggleId(prev, vehicle.id));
        anchorIdRef.current = vehicle.id;
      }
      return;
    }
    anchorIdRef.current = vehicle.id;
    router.push(`/admin/veiculos/${vehicle.id}`);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative min-w-[200px] max-w-xs flex-1">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <Input
            placeholder="Buscar por título, marca, slug…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            disabled={isPending}
            className="pl-9 pr-8 border-facil-border bg-facil-card"
          />
          {search ? (
            <button
              type="button"
              onClick={() => setSearch("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>

        <AdminFilterSheet
          activeCount={activeFilterCount}
          disabled={isPending}
          onApply={applyDraftFilters}
          onClear={clearFilters}
          advancedDefaultOpen={hasAdvancedFilters}
          basicSection={
            <>
              <div>
                <FilterFieldLabel>Status</FilterFieldLabel>
                <MultiSelect
                  options={STATUS_OPTIONS}
                  value={draft.statuses}
                  onChange={(statuses) => setDraft((d) => ({ ...d, statuses }))}
                  placeholder="Todos os status"
                  searchPlaceholder="Buscar status…"
                />
              </div>
              <div>
                <FilterFieldLabel>Marca</FilterFieldLabel>
                <MultiSelect
                  options={brands.map((b) => ({ value: b.id, label: b.name }))}
                  value={draft.brandIds}
                  onChange={(brandIds) => setDraft((d) => ({ ...d, brandIds }))}
                  placeholder="Todas as marcas"
                  searchPlaceholder="Buscar marca…"
                />
              </div>
              <div>
                <FilterFieldLabel>Tipo</FilterFieldLabel>
                <MultiSelect
                  options={TYPE_OPTIONS}
                  value={draft.types}
                  onChange={(types) => setDraft((d) => ({ ...d, types }))}
                  placeholder="Todos os tipos"
                  searchPlaceholder="Buscar tipo…"
                />
              </div>
            </>
          }
          advancedSection={
            <>
              <div>
                <FilterFieldLabel>Destaque</FilterFieldLabel>
                <MultiSelect
                  options={FEATURED_OPTIONS}
                  value={draft.featured}
                  onChange={(featured) => setDraft((d) => ({ ...d, featured }))}
                  placeholder="Todos"
                />
              </div>
              <div>
                <FilterFieldLabel>Combustível</FilterFieldLabel>
                <MultiSelect
                  options={FUEL_OPTIONS}
                  value={draft.fuelTypes}
                  onChange={(fuelTypes) => setDraft((d) => ({ ...d, fuelTypes }))}
                  placeholder="Todos"
                  searchPlaceholder="Buscar combustível…"
                />
              </div>
              <div>
                <FilterFieldLabel>Câmbio</FilterFieldLabel>
                <MultiSelect
                  options={TRANSMISSION_OPTIONS}
                  value={draft.transmissions}
                  onChange={(transmissions) => setDraft((d) => ({ ...d, transmissions }))}
                  placeholder="Todos"
                  searchPlaceholder="Buscar câmbio…"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <FilterFieldLabel>Preço mín.</FilterFieldLabel>
                  <Input
                    type="number"
                    min={0}
                    inputMode="numeric"
                    placeholder="0"
                    value={draft.priceMin}
                    onChange={(e) => setDraft((d) => ({ ...d, priceMin: e.target.value }))}
                    className="h-9 border-facil-border bg-facil-card"
                  />
                </div>
                <div>
                  <FilterFieldLabel>Preço máx.</FilterFieldLabel>
                  <Input
                    type="number"
                    min={0}
                    inputMode="numeric"
                    placeholder="—"
                    value={draft.priceMax}
                    onChange={(e) => setDraft((d) => ({ ...d, priceMax: e.target.value }))}
                    className="h-9 border-facil-border bg-facil-card"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <FilterFieldLabel>Ano mín.</FilterFieldLabel>
                  <Input
                    type="number"
                    min={1900}
                    max={2100}
                    inputMode="numeric"
                    placeholder="—"
                    value={draft.yearMin}
                    onChange={(e) => setDraft((d) => ({ ...d, yearMin: e.target.value }))}
                    className="h-9 border-facil-border bg-facil-card"
                  />
                </div>
                <div>
                  <FilterFieldLabel>Ano máx.</FilterFieldLabel>
                  <Input
                    type="number"
                    min={1900}
                    max={2100}
                    inputMode="numeric"
                    placeholder="—"
                    value={draft.yearMax}
                    onChange={(e) => setDraft((d) => ({ ...d, yearMax: e.target.value }))}
                    className="h-9 border-facil-border bg-facil-card"
                  />
                </div>
              </div>
            </>
          }
        />

        {hasActiveFilters ? (
          <Button variant="ghost" size="sm" disabled={isPending} onClick={clearFilters}>
            Limpar filtros
          </Button>
        ) : null}
      </div>

      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        {totalCount} veículo(s) encontrado(s)
        {isPending ? " · atualizando…" : ""}
      </p>

      {/* Desktop table */}
      <div
        className="hidden overflow-hidden rounded-xl border border-facil-border bg-facil-card shadow-sm md:block"
        tabIndex={0}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a") {
            e.preventDefault();
            setSelectedIds(new Set(vehicleIds));
          }
        }}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-facil-border bg-facil-surface">
              <tr>
                <th className="admin-table-header">Imagem</th>
                <th className="admin-table-header">Título</th>
                <th className="admin-table-header">Marca</th>
                <th className="admin-table-header">Status</th>
                {canWrite ? <th className="admin-table-header">Alterar status</th> : null}
                <th className="admin-table-header">Preço</th>
                <th className="admin-table-header w-12">Ações</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.length === 0 ? (
                <tr>
                  <td colSpan={canWrite ? 7 : 6} className="py-12 text-center text-sm text-facil-muted">
                    Nenhum veículo encontrado.
                  </td>
                </tr>
              ) : (
                vehicles.map((v, i) => (
                  <tr
                    key={v.id}
                    className={cn(
                      "admin-row-enter cursor-pointer border-t border-facil-border hover:bg-facil-surface/50",
                      selectedIds.has(v.id) && "bg-facil-orange-light/50",
                    )}
                    style={{ animationDelay: `${Math.min(i, 12) * 40}ms` }}
                    onClick={(e) => handleRowClick(v, e)}
                  >
                    <td className="admin-table-cell">
                      {v.images[0] ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={v.images[0].url}
                          alt={v.title}
                          className="h-12 w-16 rounded-md object-cover"
                        />
                      ) : (
                        <div className="flex h-12 w-16 items-center justify-center rounded-md bg-facil-surface text-facil-muted">
                          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={1.5}
                              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                            />
                          </svg>
                        </div>
                      )}
                    </td>
                    <td className="admin-table-cell font-medium text-foreground">{v.title}</td>
                    <td className="admin-table-cell text-facil-muted">{v.brand.name}</td>
                    <td className="admin-table-cell">
                      <StatusBadge status={v.status} />
                    </td>
                    {canWrite ? (
                      <td className="admin-table-cell" onClick={(e) => e.stopPropagation()}>
                        <QuickStatusMenu vehicleId={v.id} currentStatus={v.status} />
                      </td>
                    ) : null}
                    <td className="admin-table-cell text-foreground">
                      {v.priceCash != null
                        ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                        : "—"}
                    </td>
                    <td className="admin-table-cell" onClick={(e) => e.stopPropagation()}>
                      <VehicleActionsMenu vehicle={v} canWrite={canWrite} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile cards */}
      <div className="grid gap-3 sm:grid-cols-2 md:hidden">
        {vehicles.length === 0 ? (
          <p className="col-span-2 py-8 text-center text-sm text-facil-muted">Nenhum veículo encontrado.</p>
        ) : (
          vehicles.map((v) => (
            <div
              key={v.id}
              className="flex cursor-pointer gap-3 rounded-xl border border-facil-border bg-facil-card p-3 shadow-sm"
              onClick={(e) => handleRowClick(v, e)}
            >
              <Link href={`/admin/veiculos/${v.id}`} className="shrink-0">
                {v.images[0] ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={v.images[0].url}
                    alt={v.title}
                    className="h-16 w-20 rounded-lg object-cover"
                  />
                ) : (
                  <div className="flex h-16 w-20 items-center justify-center rounded-lg bg-facil-surface text-facil-muted">
                    <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                      />
                    </svg>
                  </div>
                )}
              </Link>
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <p className="truncate text-sm font-medium text-foreground">{v.title}</p>
                  <div onClick={(e) => e.stopPropagation()}>
                    <VehicleActionsMenu vehicle={v} canWrite={canWrite} />
                  </div>
                </div>
                <p className="text-xs text-facil-muted">{v.brand.name}</p>
                <div className="mt-1.5 flex items-center justify-between gap-2">
                  <StatusBadge status={v.status} />
                  <span className="text-xs font-medium text-foreground">
                    {v.priceCash != null
                      ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                      : "—"}
                  </span>
                </div>
                {canWrite ? (
                  <div className="mt-2">
                    <QuickStatusMenu vehicleId={v.id} currentStatus={v.status} />
                  </div>
                ) : null}
              </div>
            </div>
          ))
        )}
      </div>

      {totalPages > 1 ? (
        <div className="flex items-center justify-between border-t border-facil-border pt-4">
          <p className="text-xs text-facil-muted">
            Página {page} de {totalPages}
          </p>
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1 || isPending}
              onClick={() => applyFilter({ page: String(page - 1) })}
            >
              ←
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages || isPending}
              onClick={() => applyFilter({ page: String(page + 1) })}
            >
              →
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
