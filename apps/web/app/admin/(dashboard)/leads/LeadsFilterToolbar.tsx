"use client";

import { useCallback, useEffect, useMemo, useState, useTransition } from "react";
import type { LeadStatus, LeadType } from "@prisma/client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Search, X } from "lucide-react";
import { format, parseISO, startOfDay, subDays } from "date-fns";
import { AdminFilterSheet, FilterFieldLabel } from "@/components/admin/AdminFilterSheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MultiSelect } from "@/components/ui/multi-select";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { DateRangePicker } from "@/components/ui/date-picker";
import { useDebounce } from "@/hooks/useDebounce";
import { serializeCsvParam } from "@/lib/query-filters";
import { cn } from "@/lib/cn";

type Seller = { id: string; name: string };

const PERIOD_CUSTOM = "custom";

const STATUS_OPTIONS: { value: LeadStatus; label: string }[] = [
  { value: "NEW", label: "Novo" },
  { value: "IN_PROGRESS", label: "Em progresso" },
  { value: "CONTACTED", label: "Contactado" },
  { value: "QUALIFIED", label: "Qualificado" },
  { value: "WON", label: "Ganho" },
  { value: "LOST", label: "Perdido" },
  { value: "SPAM", label: "Spam" },
];

const TYPE_OPTIONS: { value: LeadType; label: string }[] = [
  { value: "CONTACT", label: "Contato" },
  { value: "VEHICLE_INTEREST", label: "Interesse veículo" },
  { value: "FINANCING", label: "Financiamento" },
  { value: "SELL_VEHICLE", label: "Vender veículo" },
  { value: "REFINANCING", label: "Refinanciamento" },
  { value: "TRADE_IN", label: "Troca" },
  { value: "CONSIGNMENT", label: "Consignação" },
  { value: "THIRD_PARTY_FINANCING", label: "Financiamento terceiros" },
];

function getPresetRange(period: string): { from: Date; to: Date } | null {
  if (period === "7d") {
    const to = startOfDay(new Date());
    return { from: startOfDay(subDays(to, 6)), to };
  }
  if (period === "30d") {
    const to = startOfDay(new Date());
    return { from: startOfDay(subDays(to, 29)), to };
  }
  return null;
}

type DraftFilters = {
  statuses: string[];
  types: string[];
  assignees: string[];
  period: string;
  from: string;
  to: string;
};

type LeadsFilterToolbarProps = {
  sellers: Seller[];
  statuses: LeadStatus[];
  types: LeadType[];
  assignees: string[];
  currentPeriod?: string;
  fromKey?: string;
  toKey?: string;
  initialSearch: string;
  totalCount?: number;
  preserveView?: boolean;
};

function filtersToDraft(
  statuses: LeadStatus[],
  types: LeadType[],
  assignees: string[],
  currentPeriod = "all",
  fromKey?: string,
  toKey?: string,
): DraftFilters {
  return {
    statuses,
    types,
    assignees,
    period: currentPeriod,
    from: fromKey ?? "",
    to: toKey ?? "",
  };
}

function countActiveFilters(
  statuses: LeadStatus[],
  types: LeadType[],
  assignees: string[],
  currentPeriod?: string,
  fromKey?: string,
  toKey?: string,
): number {
  let n = 0;
  if (statuses.length) n++;
  if (types.length) n++;
  if (assignees.length) n++;
  if ((currentPeriod && currentPeriod !== "all") || (fromKey && toKey)) n++;
  return n;
}

export function LeadsFilterToolbar({
  sellers,
  statuses,
  types,
  assignees,
  currentPeriod = "all",
  fromKey,
  toKey,
  initialSearch,
  totalCount,
  preserveView = false,
}: LeadsFilterToolbarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [search, setSearch] = useState(initialSearch);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const debouncedSearch = useDebounce(search, 350);
  const [draft, setDraft] = useState<DraftFilters>(() =>
    filtersToDraft(statuses, types, assignees, currentPeriod, fromKey, toKey),
  );

  const assigneeOptions = useMemo(
    () => [
      { value: "none", label: "Sem responsável" },
      ...sellers.map((s) => ({ value: s.id, label: s.name })),
    ],
    [sellers],
  );

  const activeFilterCount = useMemo(
    () => countActiveFilters(statuses, types, assignees, currentPeriod, fromKey, toKey),
    [statuses, types, assignees, currentPeriod, fromKey, toKey],
  );

  const hasAdvancedFilters =
    (currentPeriod && currentPeriod !== "all") || !!(fromKey && toKey);

  useEffect(() => {
    setSearch(initialSearch);
  }, [initialSearch]);

  useEffect(() => {
    setDraft(filtersToDraft(statuses, types, assignees, currentPeriod, fromKey, toKey));
  }, [statuses, types, assignees, currentPeriod, fromKey, toKey]);

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

  function applyDraftFilters() {
    pushSearchParams((sp) => {
      const setCsv = (key: string, values: string[]) => {
        const serialized = serializeCsvParam(values);
        if (serialized) sp.set(key, serialized);
        else sp.delete(key);
      };

      setCsv("status", draft.statuses);
      setCsv("tipo", draft.types);
      setCsv("responsavel", draft.assignees);

      if (draft.period && draft.period !== "all" && draft.period !== PERIOD_CUSTOM) {
        sp.set("periodo", draft.period);
        const preset = getPresetRange(draft.period);
        if (preset) {
          sp.set("from", format(preset.from, "yyyy-MM-dd"));
          sp.set("to", format(preset.to, "yyyy-MM-dd"));
        }
      } else if (draft.from && draft.to) {
        sp.delete("periodo");
        sp.set("from", draft.from);
        sp.set("to", draft.to);
      } else {
        sp.delete("periodo");
        sp.delete("from");
        sp.delete("to");
      }

      sp.set("page", "1");
    });
  }

  function clearFilters() {
    startTransition(() => {
      const sp = new URLSearchParams();
      const q = search.trim();
      if (q) sp.set("q", q);
      if (preserveView && searchParams.get("view") === "kanban") {
        sp.set("view", "kanban");
      }
      const qs = sp.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname);
      setDraft(filtersToDraft([], [], [], "all"));
      router.refresh();
    });
  }

  const qActive = (searchParams.get("q") ?? "").trim();
  const hasActiveFilters = activeFilterCount > 0 || !!qActive;

  const presetRange = useMemo(() => getPresetRange(draft.period), [draft.period]);
  const rangeFrom = draft.from ? parseISO(`${draft.from}T12:00:00`) : presetRange?.from;
  const rangeTo = draft.to ? parseISO(`${draft.to}T12:00:00`) : presetRange?.to;

  const periodSelectValue =
    draft.period === "7d"
      ? "7d"
      : draft.period === "30d"
        ? "30d"
        : draft.from && draft.to
          ? PERIOD_CUSTOM
          : draft.period || "all";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative min-w-[200px] max-w-xs flex-1">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-facil-muted" />
          <Input
            placeholder="Buscar por nome, telefone…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            disabled={isPending}
            className="pl-9 pr-8"
          />
          {search ? (
            <button
              type="button"
              onClick={() => setSearch("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-facil-muted hover:text-foreground"
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
                <FilterFieldLabel>Tipo</FilterFieldLabel>
                <MultiSelect
                  options={TYPE_OPTIONS}
                  value={draft.types}
                  onChange={(types) => setDraft((d) => ({ ...d, types }))}
                  placeholder="Todos os tipos"
                  searchPlaceholder="Buscar tipo…"
                />
              </div>
              <div>
                <FilterFieldLabel>Responsável</FilterFieldLabel>
                <MultiSelect
                  options={assigneeOptions}
                  value={draft.assignees}
                  onChange={(assignees) => setDraft((d) => ({ ...d, assignees }))}
                  placeholder="Todos os responsáveis"
                  searchPlaceholder="Buscar responsável…"
                />
              </div>
            </>
          }
          advancedSection={
            <>
              <div>
                <FilterFieldLabel>Período</FilterFieldLabel>
                <Select
                  value={periodSelectValue}
                  disabled={isPending}
                  onValueChange={(v) => {
                    if (v === PERIOD_CUSTOM) {
                      setCalendarOpen(true);
                      setDraft((d) => ({ ...d, period: PERIOD_CUSTOM }));
                      return;
                    }
                    const preset = v === "7d" || v === "30d" ? getPresetRange(v) : null;
                    setDraft((d) => ({
                      ...d,
                      period: v,
                      from: preset ? format(preset.from, "yyyy-MM-dd") : "",
                      to: preset ? format(preset.to, "yyyy-MM-dd") : "",
                    }));
                  }}
                >
                  <SelectTrigger className="h-9 w-full border-facil-border bg-facil-card">
                    <span
                      className={cn(
                        "truncate",
                        periodSelectValue === "all" && "text-facil-muted",
                      )}
                    >
                      {periodSelectValue === "7d"
                        ? "Últimos 7 dias"
                        : periodSelectValue === "30d"
                          ? "Últimos 30 dias"
                          : periodSelectValue === PERIOD_CUSTOM
                            ? "Intervalo personalizado…"
                            : "Todo o período"}
                    </span>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todo o período</SelectItem>
                    <SelectItem value="7d">Últimos 7 dias</SelectItem>
                    <SelectItem value="30d">Últimos 30 dias</SelectItem>
                    <SelectItem value={PERIOD_CUSTOM}>Intervalo personalizado…</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <DateRangePicker
                key={`${periodSelectValue}-${draft.from}-${draft.to}`}
                from={rangeFrom}
                to={rangeTo}
                disabled={isPending}
                open={calendarOpen}
                onOpenChange={setCalendarOpen}
                className="w-full"
                onApply={({ from: f, to: t }) =>
                  setDraft((d) => ({
                    ...d,
                    period: PERIOD_CUSTOM,
                    from: f ? format(f, "yyyy-MM-dd") : "",
                    to: t ? format(t, "yyyy-MM-dd") : "",
                  }))
                }
              />
            </>
          }
        />

        {hasActiveFilters ? (
          <Button variant="ghost" size="sm" onClick={clearFilters} disabled={isPending}>
            Limpar filtros
          </Button>
        ) : null}
      </div>

      {totalCount != null ? (
        <span className="text-sm text-facil-muted">
          {totalCount} resultado(s)
          {isPending ? " · atualizando…" : ""}
        </span>
      ) : null}
    </div>
  );
}
