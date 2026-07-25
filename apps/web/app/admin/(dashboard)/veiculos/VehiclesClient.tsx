"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import Link from "next/link";
import type { VehicleStatus } from "@prisma/client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ChevronDown, ExternalLink, MoreHorizontal, Search, X } from "lucide-react";
import { toast } from "sonner";
import { quickUpdateVehicleStatusAction } from "@/features/vehicle/server/mutations";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { ArchiveVehicleButton } from "./ArchiveVehicleButton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { useDebounce } from "@/hooks/useDebounce";
import { cn } from "@/lib/cn";

type VehicleRow = {
  id: string;
  slug: string;
  title: string;
  status: string;
  priceCash: number | null;
  brand: { name: string };
  images: { url: string }[];
};

const STATUS_OPTIONS: { value: VehicleStatus; label: string }[] = [
  { value: "DRAFT", label: "Rascunho" },
  { value: "PUBLISHED", label: "Publicado" },
  { value: "RESERVED", label: "Reservado" },
  { value: "SOLD", label: "Vendido" },
  { value: "ARCHIVED", label: "Arquivado" },
];

const QUICK_STATUS_OPTIONS: { value: VehicleStatus; label: string }[] = [
  { value: "DRAFT", label: "Rascunho" },
  { value: "PUBLISHED", label: "Publicado" },
  { value: "RESERVED", label: "Reservado" },
  { value: "SOLD", label: "Vendido" },
  { value: "ARCHIVED", label: "Arquivado" },
];

interface VehiclesClientProps {
  vehicles: VehicleRow[];
  totalCount: number;
  page: number;
  pageSize: number;
  currentStatus?: VehicleStatus;
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
  currentStatus,
  initialSearch,
  canWrite = true,
}: VehiclesClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [search, setSearch] = useState(initialSearch);
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

  function clearFilters() {
    startTransition(() => {
      router.push("/admin/veiculos");
      setSearch("");
    });
  }

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const qActive = (searchParams.get("q") ?? "").trim();
  const hasActiveFilters = !!(currentStatus || qActive);

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

        <Select
          value={currentStatus ?? "all"}
          disabled={isPending}
          onValueChange={(v) => applyFilter({ status: v === "all" ? undefined : v })}
        >
          <SelectTrigger className="h-9 w-[180px] border-facil-border bg-facil-card">
            <span className={cn("truncate", !currentStatus && "text-facil-muted")}>
              {currentStatus
                ? STATUS_OPTIONS.find((s) => s.value === currentStatus)?.label ?? currentStatus
                : "Status"}
            </span>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos os status</SelectItem>
            {STATUS_OPTIONS.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

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
      <div className="hidden overflow-hidden rounded-xl border border-facil-border bg-facil-card shadow-sm md:block">
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
                vehicles.map((v) => (
                  <tr
                    key={v.id}
                    className="border-t border-facil-border hover:bg-facil-surface/50"
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
                      <td className="admin-table-cell">
                        <QuickStatusMenu vehicleId={v.id} currentStatus={v.status} />
                      </td>
                    ) : null}
                    <td className="admin-table-cell text-foreground">
                      {v.priceCash != null
                        ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                        : "—"}
                    </td>
                    <td className="admin-table-cell">
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
              className="flex gap-3 rounded-xl border border-facil-border bg-facil-card p-3 shadow-sm"
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
                  <Link
                    href={`/admin/veiculos/${v.id}`}
                    className="truncate text-sm font-medium text-foreground hover:text-facil-orange"
                  >
                    {v.title}
                  </Link>
                  <VehicleActionsMenu vehicle={v} canWrite={canWrite} />
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
