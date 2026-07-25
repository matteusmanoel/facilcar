"use client";

import { useState, useEffect, useTransition, useCallback, useMemo } from "react";
import Link from "next/link";
import type { LeadStatus, LeadType } from "@prisma/client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Search, X } from "lucide-react";
import { format, parseISO, startOfDay, subDays } from "date-fns";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { DateRangePicker } from "@/components/ui/date-picker";
import { useDebounce } from "@/hooks/useDebounce";
import { cn } from "@/lib/cn";

type Lead = {
  id: string;
  name: string;
  phone: string;
  email: string | null;
  type: string;
  status: string;
  source: string;
  message: string | null;
  internalNote: string | null;
  createdAt: string;
  assignedToUser: { id: string; name: string } | null;
  vehicle: { title: string; slug: string } | null;
};

type Seller = { id: string; name: string };

const WA_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
  </svg>
);

const PERIOD_CUSTOM = "custom";

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

const STATUS_LABELS: Record<LeadStatus, string> = {
  NEW: "Novo",
  IN_PROGRESS: "Em progresso",
  CONTACTED: "Contactado",
  QUALIFIED: "Qualificado",
  WON: "Ganho",
  LOST: "Perdido",
  SPAM: "Spam",
};

const TYPE_LABELS: Record<LeadType, string> = {
  CONTACT: "Contato",
  VEHICLE_INTEREST: "Interesse veículo",
  FINANCING: "Financiamento",
  SELL_VEHICLE: "Vender veículo",
  REFINANCING: "Refinanciamento",
  TRADE_IN: "Troca",
  CONSIGNMENT: "Consignação",
  THIRD_PARTY_FINANCING: "Financiamento terceiros",
};

interface LeadsClientProps {
  leads: Lead[];
  totalCount: number;
  page: number;
  pageSize: number;
  currentStatus?: LeadStatus;
  currentType?: LeadType;
  currentAssignee?: string;
  sellers: Seller[];
  currentPeriod?: string;
  fromKey?: string;
  toKey?: string;
  initialSearch: string;
}

export function LeadsClient({
  leads,
  totalCount,
  page,
  pageSize,
  currentStatus,
  currentType,
  currentAssignee,
  sellers,
  currentPeriod = "all",
  fromKey,
  toKey,
  initialSearch,
}: LeadsClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const [search, setSearch] = useState(initialSearch);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const debouncedSearch = useDebounce(search, 350);

  useEffect(() => {
    setSearch(initialSearch);
  }, [initialSearch]);

  useEffect(() => {
    const currentQ = searchParams.get("q") ?? "";
    if (debouncedSearch === currentQ) return;
    startTransition(() => {
      const sp = new URLSearchParams(searchParams.toString());
      if (debouncedSearch.trim()) sp.set("q", debouncedSearch.trim());
      else sp.delete("q");
      sp.set("page", "1");
      router.replace(`${pathname}?${sp.toString()}`);
    });
  }, [debouncedSearch, pathname, router, searchParams]);

  const pushSearchParams = useCallback(
    (mutate: (sp: URLSearchParams) => void) => {
      startTransition(() => {
        const sp = new URLSearchParams(searchParams.toString());
        mutate(sp);
        const qs = sp.toString();
        router.push(qs ? `${pathname}?${qs}` : pathname);
      });
    },
    [pathname, router, searchParams],
  );

  function applyFilter(updates: Record<string, string | undefined>) {
    pushSearchParams((sp: URLSearchParams) => {
      Object.entries(updates).forEach(([k, v]) => {
        if (v === undefined || v === "" || v === "all") sp.delete(k);
        else sp.set(k, v);
      });

      const hasPeriodUpdate = Object.prototype.hasOwnProperty.call(updates, "periodo");
      const hasDateUpdate =
        Object.prototype.hasOwnProperty.call(updates, "from") ||
        Object.prototype.hasOwnProperty.call(updates, "to");

      if (hasPeriodUpdate && !hasDateUpdate) {
        const period = updates.periodo;
        if (period === "7d" || period === "30d") {
          const preset = getPresetRange(period);
          if (preset) {
            sp.set("from", format(preset.from, "yyyy-MM-dd"));
            sp.set("to", format(preset.to, "yyyy-MM-dd"));
          }
        } else if (!period || period === "all") {
          sp.delete("from");
          sp.delete("to");
        }
      }

      if (hasDateUpdate && !hasPeriodUpdate) {
        sp.delete("periodo");
      }

      if (!Object.prototype.hasOwnProperty.call(updates, "page")) {
        sp.set("page", "1");
      }
    });
  }

  function clearFilters() {
    startTransition(() => {
      router.push("/admin/leads");
      setSearch("");
    });
  }

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const qActive = (searchParams.get("q") ?? "").trim();
  const hasActiveFilters = !!(
    currentStatus ||
    currentType ||
    currentAssignee ||
    (currentPeriod && currentPeriod !== "all") ||
    (fromKey && toKey) ||
    qActive
  );

  const presetRange = useMemo(
    () => getPresetRange(currentPeriod),
    [currentPeriod],
  );

  const rangeFrom = fromKey
    ? parseISO(`${fromKey}T12:00:00`)
    : presetRange?.from;
  const rangeTo = toKey
    ? parseISO(`${toKey}T12:00:00`)
    : presetRange?.to;

  const periodSelectValue =
    currentPeriod === "7d"
      ? "7d"
      : currentPeriod === "30d"
        ? "30d"
        : fromKey && toKey
          ? PERIOD_CUSTOM
          : currentPeriod || "all";

  const assigneeLabel =
    currentAssignee === "none"
      ? "Sem responsável"
      : currentAssignee
        ? sellers.find((s) => s.id === currentAssignee)?.name
        : undefined;

  return (
    <>
      <div className="flex flex-col gap-3">
        {/* Search row */}
        <div className="relative w-full">
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

        {/* Filters row */}
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <Select
            value={currentStatus ?? "all"}
            disabled={isPending}
            onValueChange={(v) => applyFilter({ status: v === "all" ? undefined : v })}
          >
            <SelectTrigger className="h-9 w-full">
              <span className={cn("truncate", !currentStatus && "text-facil-muted")}>
                {currentStatus ? STATUS_LABELS[currentStatus] : "Status"}
              </span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos os status</SelectItem>
              <SelectItem value="NEW">Novo</SelectItem>
              <SelectItem value="IN_PROGRESS">Em progresso</SelectItem>
              <SelectItem value="CONTACTED">Contactado</SelectItem>
              <SelectItem value="QUALIFIED">Qualificado</SelectItem>
              <SelectItem value="WON">Ganho</SelectItem>
              <SelectItem value="LOST">Perdido</SelectItem>
              <SelectItem value="SPAM">Spam</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={currentType ?? "all"}
            disabled={isPending}
            onValueChange={(v) => applyFilter({ tipo: v === "all" ? undefined : v })}
          >
            <SelectTrigger className="h-9 w-full">
              <span className={cn("truncate", !currentType && "text-facil-muted")}>
                {currentType ? TYPE_LABELS[currentType] : "Tipo"}
              </span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos os tipos</SelectItem>
              <SelectItem value="CONTACT">Contato</SelectItem>
              <SelectItem value="VEHICLE_INTEREST">Interesse veículo</SelectItem>
              <SelectItem value="FINANCING">Financiamento</SelectItem>
              <SelectItem value="SELL_VEHICLE">Vender veículo</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={currentAssignee ?? "all"}
            disabled={isPending}
            onValueChange={(v) => applyFilter({ responsavel: v === "all" ? undefined : v })}
          >
            <SelectTrigger className="h-9 w-full">
              <span className={cn("truncate", !currentAssignee && "text-facil-muted")}>
                {assigneeLabel ?? "Responsável"}
              </span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos os responsáveis</SelectItem>
              <SelectItem value="none">Sem responsável</SelectItem>
              {sellers.map((seller) => (
                <SelectItem key={seller.id} value={seller.id}>
                  {seller.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={periodSelectValue}
            disabled={isPending}
            onValueChange={(v) => {
              if (v === PERIOD_CUSTOM) {
                setCalendarOpen(true);
                return;
              }
              applyFilter({ periodo: v === "all" ? undefined : v });
            }}
          >
            <SelectTrigger className="h-9 w-full">
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
                      : "Período"}
              </span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todo o período</SelectItem>
              <SelectItem value="7d">Últimos 7 dias</SelectItem>
              <SelectItem value="30d">Últimos 30 dias</SelectItem>
              <SelectItem value={PERIOD_CUSTOM}>Intervalo personalizado…</SelectItem>
            </SelectContent>
          </Select>

          <DateRangePicker
            key={`${periodSelectValue}-${fromKey ?? ""}-${toKey ?? ""}`}
            from={rangeFrom}
            to={rangeTo}
            disabled={isPending}
            open={calendarOpen}
            onOpenChange={setCalendarOpen}
            className="w-full"
            onApply={({ from: f, to: t }) =>
              applyFilter({
                from: f ? format(f, "yyyy-MM-dd") : undefined,
                to: t ? format(t, "yyyy-MM-dd") : undefined,
                periodo: undefined,
              })
            }
          />

          {hasActiveFilters ? (
            <Button variant="outline" size="sm" onClick={clearFilters} disabled={isPending} className="w-full sm:w-auto">
              <X className="mr-1 h-3.5 w-3.5" />
              Limpar filtros
            </Button>
          ) : null}
        </div>

        <span className="text-sm text-facil-muted">
          {totalCount} resultado(s)
          {isPending ? " · atualizando…" : ""}
        </span>
      </div>

      <div className="overflow-hidden rounded-xl border border-facil-border bg-facil-card shadow-sm">
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full text-sm">
            <thead className="border-b border-facil-border bg-facil-surface">
              <tr>
                <th className="admin-table-header">Data</th>
                <th className="admin-table-header">Nome</th>
                <th className="admin-table-header">Telefone</th>
                <th className="admin-table-header">Tipo</th>
                <th className="admin-table-header">Status</th>
                <th className="admin-table-header">Responsável</th>
                <th className="admin-table-header">Veículo</th>
                <th className="admin-table-header">Ações</th>
              </tr>
            </thead>
            <tbody>
              {leads.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-sm text-zinc-400">
                    Nenhum lead encontrado.
                  </td>
                </tr>
              ) : (
                leads.map((lead) => {
                  const phone = lead.phone.replace(/\D/g, "");
                  const waUrl = phone
                    ? `https://wa.me/${phone}?text=${encodeURIComponent(`Olá ${lead.name}, aqui é da FácilCar!`)}`
                    : null;
                  return (
                    <tr
                      key={lead.id}
                      className="border-t border-facil-border hover:bg-facil-surface/70"
                    >
                      <td className="admin-table-cell text-facil-muted">
                        {new Date(lead.createdAt).toLocaleDateString("pt-BR")}
                      </td>
                      <td className="admin-table-cell font-medium text-foreground">
                        {lead.name}
                      </td>
                      <td className="admin-table-cell text-foreground/80">
                        {lead.phone}
                      </td>
                      <td className="admin-table-cell">
                        <StatusBadge status={lead.type} type="type" />
                      </td>
                      <td className="admin-table-cell">
                        <StatusBadge status={lead.status} />
                      </td>
                      <td className="admin-table-cell text-facil-muted">
                        {lead.assignedToUser?.name ?? "—"}
                      </td>
                      <td className="admin-table-cell max-w-[160px] text-facil-muted">
                        <span className="line-clamp-1">{lead.vehicle?.title ?? "—"}</span>
                      </td>
                      <td className="admin-table-cell" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/admin/leads/${lead.id}`}
                            className="text-xs font-medium text-facil-orange hover:underline"
                          >
                            Detalhes
                          </Link>
                          {waUrl ? (
                            <a
                              href={waUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex h-6 w-6 items-center justify-center rounded-full bg-green-500 text-white hover:bg-green-600"
                            >
                              {WA_ICON}
                            </a>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="divide-y divide-facil-border md:hidden">
          {leads.length === 0 ? (
            <div className="py-10 text-center text-sm text-facil-muted">Nenhum lead encontrado.</div>
          ) : (
            leads.map((lead) => {
              const phone = lead.phone.replace(/\D/g, "");
              const waUrl = phone
                ? `https://wa.me/${phone}?text=${encodeURIComponent(`Olá ${lead.name}, aqui é da FácilCar!`)}`
                : null;
              return (
                <div
                  key={lead.id}
                  className="px-4 py-3 hover:bg-facil-surface/70"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-foreground">{lead.name}</p>
                      <p className="text-xs text-facil-muted">{lead.phone}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      <StatusBadge status={lead.status} />
                      {waUrl ? (
                        <a
                          href={waUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="flex h-6 w-6 items-center justify-center rounded-full bg-green-500 text-white"
                        >
                          {WA_ICON}
                        </a>
                      ) : null}
                    </div>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-facil-muted">
                    <StatusBadge status={lead.type} type="type" />
                    <span>·</span>
                    <span>{new Date(lead.createdAt).toLocaleDateString("pt-BR")}</span>
                    {lead.assignedToUser ? (
                      <>
                        <span>·</span>
                        <span>{lead.assignedToUser.name}</span>
                      </>
                    ) : null}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {totalPages > 1 ? (
          <div className="flex items-center justify-between border-t border-facil-border px-4 py-3">
            <p className="text-xs text-facil-muted">
              Página {page} de {totalPages} · {totalCount} leads
            </p>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1 || isPending}
                onClick={() =>
                  pushSearchParams((sp: URLSearchParams) => {
                    sp.set("page", String(page - 1));
                  })
                }
              >
                ←
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages || isPending}
                onClick={() =>
                  pushSearchParams((sp: URLSearchParams) => {
                    sp.set("page", String(page + 1));
                  })
                }
              >
                →
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </>
  );
}
