"use client";

import { useTransition, useCallback, useState, useRef } from "react";
import type { MouseEvent } from "react";
import type { LeadStatus, LeadType } from "@prisma/client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { Button } from "@/components/ui/button";
import { LeadsFilterToolbar } from "./LeadsFilterToolbar";
import { cn } from "@/lib/cn";
import { rangeIds, toggleId, unionIds } from "@/lib/range-select";
import { useClearSelectionOnEscape } from "@/hooks/useClearSelectionOnEscape";

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
  temperature?: string | null;
  createdAt: string;
  assignedToUser: { id: string; name: string } | null;
  vehicle: { title: string; slug: string } | null;
  vehicleLabel?: string | null;
};

type Seller = { id: string; name: string };

const TEMPERATURE_LABELS: Record<string, string> = {
  HOT: "Quente",
  WARM: "Morno",
  COLD: "Frio",
};

const TEMPERATURE_CLASSES: Record<string, string> = {
  HOT: "bg-red-100 text-red-800 dark:bg-red-950/40 dark:text-red-300",
  WARM: "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300",
  COLD: "bg-sky-100 text-sky-800 dark:bg-sky-950/40 dark:text-sky-300",
};

function TemperatureBadge({ temperature }: { temperature: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${TEMPERATURE_CLASSES[temperature] ?? "bg-zinc-100 text-zinc-600"}`}
    >
      {TEMPERATURE_LABELS[temperature] ?? temperature}
    </span>
  );
}

const WA_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
  </svg>
);

interface LeadsClientProps {
  leads: Lead[];
  totalCount: number;
  page: number;
  pageSize: number;
  statuses: LeadStatus[];
  types: LeadType[];
  assignees: string[];
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
  statuses,
  types,
  assignees,
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
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const anchorIdRef = useRef<string | null>(null);
  const clearSelection = useCallback(() => setSelectedIds(new Set()), []);
  useClearSelectionOnEscape(clearSelection, selectedIds.size > 0);

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

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const leadIds = leads.map((l) => l.id);

  function handleRowClick(lead: Lead, event: MouseEvent) {
    if (event.shiftKey || event.metaKey || event.ctrlKey) {
      event.preventDefault();
      if (event.shiftKey) {
        const range = rangeIds(leadIds, anchorIdRef.current, lead.id);
        setSelectedIds((prev) => unionIds(prev, range));
      } else {
        setSelectedIds((prev) => toggleId(prev, lead.id));
        anchorIdRef.current = lead.id;
      }
      return;
    }
    anchorIdRef.current = lead.id;
    router.push(`/admin/leads/${lead.id}`);
  }

  return (
    <>
      <LeadsFilterToolbar
        sellers={sellers}
        statuses={statuses}
        types={types}
        assignees={assignees}
        currentPeriod={currentPeriod}
        fromKey={fromKey}
        toKey={toKey}
        initialSearch={initialSearch}
        totalCount={totalCount}
      />

      <div
        className="overflow-hidden rounded-xl border border-facil-border bg-facil-card shadow-sm"
        tabIndex={0}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a") {
            e.preventDefault();
            setSelectedIds(new Set(leadIds));
          }
        }}
      >
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
                  <td colSpan={8} className="py-12 text-center text-sm text-facil-muted">
                    Nenhum lead encontrado.
                  </td>
                </tr>
              ) : (
                leads.map((lead, i) => {
                  const phone = lead.phone.replace(/\D/g, "");
                  const waUrl = phone
                    ? `https://wa.me/${phone}?text=${encodeURIComponent(`Olá ${lead.name}, aqui é da FácilCar!`)}`
                    : null;
                  return (
                    <tr
                      key={lead.id}
                      className={cn(
                        "admin-row-enter cursor-pointer border-t border-facil-border hover:bg-facil-surface/70",
                        selectedIds.has(lead.id) && "bg-facil-orange-light/50",
                      )}
                      style={{ animationDelay: `${Math.min(i, 12) * 40}ms` }}
                      onClick={(e) => handleRowClick(lead, e)}
                    >
                      <td className="admin-table-cell text-facil-muted">
                        {new Date(lead.createdAt).toLocaleDateString("pt-BR")}
                      </td>
                      <td className="admin-table-cell font-medium text-foreground">
                        <div className="flex items-center gap-1.5">
                          <span>{lead.name}</span>
                          {lead.temperature ? (
                            <TemperatureBadge temperature={lead.temperature} />
                          ) : null}
                        </div>
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
                        <span className="line-clamp-1">
                          {lead.vehicleLabel ?? lead.vehicle?.title ?? "—"}
                        </span>
                      </td>
                      <td className="admin-table-cell" onClick={(e) => e.stopPropagation()}>
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
                  className={cn(
                    "cursor-pointer px-4 py-3 hover:bg-facil-surface/70",
                    selectedIds.has(lead.id) && "bg-facil-orange-light/50",
                  )}
                  onClick={(e) => handleRowClick(lead, e)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <p className="truncate font-medium text-foreground">{lead.name}</p>
                        {lead.temperature ? (
                          <TemperatureBadge temperature={lead.temperature} />
                        ) : null}
                      </div>
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
                  pushSearchParams((sp) => {
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
                  pushSearchParams((sp) => {
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
