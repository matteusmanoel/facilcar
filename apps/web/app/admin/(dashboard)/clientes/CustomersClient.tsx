"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import { Pencil, Plus, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useDebounce } from "@/hooks/useDebounce";
import { CustomerFormDialog } from "./CustomerFormDialog";

type CustomerRow = {
  id: string;
  name: string;
  phone: string;
  email: string | null;
  createdAt: string;
  _count: { leads: number };
};

type Props = {
  customers: CustomerRow[];
  totalCount: number;
  page: number;
  pageSize: number;
  initialSearch: string;
  canWrite: boolean;
};

function formatPhone(phone: string): string {
  if (phone.length === 11) {
    return `(${phone.slice(0, 2)}) ${phone.slice(2, 7)}-${phone.slice(7)}`;
  }
  if (phone.length === 10) {
    return `(${phone.slice(0, 2)}) ${phone.slice(2, 6)}-${phone.slice(6)}`;
  }
  return phone;
}

export function CustomersClient({
  customers,
  totalCount,
  page,
  pageSize,
  initialSearch,
  canWrite,
}: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(initialSearch);
  const debouncedSearch = useDebounce(search, 300);
  const [, startTransition] = useTransition();
  const [formOpen, setFormOpen] = useState(false);
  const [formMode, setFormMode] = useState<"create" | "edit">("create");
  const [editCustomer, setEditCustomer] = useState<CustomerRow | null>(null);

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  const updateParams = useCallback(
    (updates: Record<string, string | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      startTransition(() => {
        router.push(`${pathname}?${params.toString()}`);
      });
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    if (debouncedSearch !== initialSearch) {
      updateParams({ q: debouncedSearch || undefined, page: "1" });
    }
  }, [debouncedSearch, initialSearch, updateParams]);

  function openCreate() {
    setFormMode("create");
    setEditCustomer(null);
    setFormOpen(true);
  }

  function openEdit(customer: CustomerRow) {
    setFormMode("edit");
    setEditCustomer(customer);
    setFormOpen(true);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nome ou telefone…"
            className="pl-9 pr-9"
          />
          {search ? (
            <button
              type="button"
              onClick={() => setSearch("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600"
            >
              <X className="h-4 w-4" />
            </button>
          ) : null}
        </div>

        {canWrite ? (
          <Button variant="primary" size="sm" onClick={openCreate}>
            <Plus className="mr-1 h-4 w-4" />
            Novo cliente
          </Button>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-xl border border-facil-border bg-facil-card shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-facil-border bg-facil-surface">
              <tr>
                <th className="admin-table-header">Nome</th>
                <th className="admin-table-header">Telefone</th>
                <th className="admin-table-header">E-mail</th>
                <th className="admin-table-header">Leads</th>
                <th className="admin-table-header">Desde</th>
                {canWrite ? <th className="admin-table-header">Ações</th> : null}
              </tr>
            </thead>
            <tbody>
              {customers.length === 0 ? (
                <tr>
                  <td
                    colSpan={canWrite ? 6 : 5}
                    className="py-10 text-center text-sm text-zinc-400"
                  >
                    Nenhum cliente encontrado.
                  </td>
                </tr>
              ) : (
                customers.map((customer) => (
                  <tr
                    key={customer.id}
                    className="border-t border-facil-border hover:bg-facil-surface/60"
                  >
                    <td className="admin-table-cell font-medium">
                      <Link
                        href={`/admin/clientes/${customer.id}`}
                        className="hover:text-facil-orange hover:underline"
                      >
                        {customer.name}
                      </Link>
                    </td>
                    <td className="admin-table-cell font-mono text-zinc-600 dark:text-zinc-300">
                      {formatPhone(customer.phone)}
                    </td>
                    <td className="admin-table-cell text-zinc-600 dark:text-zinc-300">
                      {customer.email ?? "—"}
                    </td>
                    <td className="admin-table-cell">
                      {customer._count.leads > 0 ? (
                        <Link
                          href={`/admin/leads?q=${encodeURIComponent(customer.phone)}`}
                          className="font-medium text-facil-orange hover:underline"
                        >
                          {customer._count.leads} lead(s)
                        </Link>
                      ) : (
                        <span className="text-zinc-400">0</span>
                      )}
                    </td>
                    <td className="admin-table-cell text-zinc-500 dark:text-zinc-400">
                      {format(parseISO(customer.createdAt), "dd/MM/yyyy", { locale: ptBR })}
                    </td>
                    {canWrite ? (
                      <td className="admin-table-cell">
                        <button
                          type="button"
                          onClick={() => openEdit(customer)}
                          className="inline-flex items-center gap-1 font-medium text-facil-orange hover:underline"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          Editar
                        </button>
                      </td>
                    ) : null}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 ? (
        <div className="flex items-center justify-between text-sm text-zinc-500">
          <span>
            {totalCount} cliente(s) · página {page} de {totalPages}
          </span>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => updateParams({ page: String(page - 1) })}
            >
              Anterior
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => updateParams({ page: String(page + 1) })}
            >
              Próxima
            </Button>
          </div>
        </div>
      ) : null}

      {canWrite ? (
        <CustomerFormDialog
          open={formOpen}
          onOpenChange={setFormOpen}
          mode={formMode}
          customer={
            editCustomer
              ? {
                  id: editCustomer.id,
                  name: editCustomer.name,
                  phone: editCustomer.phone,
                  email: editCustomer.email,
                  leadCount: editCustomer._count.leads,
                }
              : undefined
          }
          onSaved={() => router.refresh()}
          onOpenExisting={(existing) => {
            setFormMode("edit");
            setEditCustomer({
              ...existing,
              createdAt: new Date().toISOString(),
              _count: { leads: existing.leadCount },
            });
            setFormOpen(true);
          }}
        />
      ) : null}
    </div>
  );
}
