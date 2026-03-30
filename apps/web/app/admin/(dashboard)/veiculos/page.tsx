import Link from "next/link";
import { Plus, ExternalLink } from "lucide-react";
import { prisma } from "@/lib/db";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/admin/StatusBadge";

export default async function AdminVeiculosPage() {
  const vehicles = await prisma.vehicle.findMany({
    orderBy: { updatedAt: "desc" },
    take: 100,
    include: {
      brand: true,
      images: { take: 1, orderBy: { sortOrder: "asc" } },
    },
  });

  return (
    <div className="admin-page admin-section">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Veículos</h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">{vehicles.length} veículo(s) no estoque</p>
        </div>
        <Link href="/admin/veiculos/novo">
          <Button variant="primary" size="sm">
            <Plus className="h-4 w-4 mr-1" />
            Novo veículo
          </Button>
        </Link>
      </div>

      {/* Desktop table */}
      <div className="hidden overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900 md:block">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-100 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-800/50">
              <tr>
                <th className="admin-table-header">Imagem</th>
                <th className="admin-table-header">Título</th>
                <th className="admin-table-header">Marca</th>
                <th className="admin-table-header">Status</th>
                <th className="admin-table-header">Preço</th>
                <th className="admin-table-header">Ações</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-sm text-zinc-400">
                    Nenhum veículo cadastrado.
                  </td>
                </tr>
              ) : (
                vehicles.map((v) => (
                  <tr key={v.id} className="border-t border-zinc-100 hover:bg-zinc-50/50 dark:border-zinc-800 dark:hover:bg-zinc-800/40">
                    <td className="admin-table-cell">
                      {v.images[0] ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={v.images[0].url}
                          alt={v.title}
                          className="h-12 w-16 rounded-md object-cover"
                        />
                      ) : (
                        <div className="flex h-12 w-16 items-center justify-center rounded-md bg-zinc-100 text-zinc-300 dark:bg-zinc-800">
                          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        </div>
                      )}
                    </td>
                    <td className="admin-table-cell font-medium text-zinc-900 dark:text-zinc-100">{v.title}</td>
                    <td className="admin-table-cell text-zinc-500 dark:text-zinc-400">{v.brand.name}</td>
                    <td className="admin-table-cell">
                      <StatusBadge status={v.status} />
                    </td>
                    <td className="admin-table-cell text-zinc-700 dark:text-zinc-300">
                      {v.priceCash != null
                        ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                        : "—"}
                    </td>
                    <td className="admin-table-cell">
                      <div className="flex items-center gap-3">
                        <Link
                          href={`/admin/veiculos/${v.id}`}
                          className="font-medium text-facil-orange hover:underline"
                        >
                          Editar
                        </Link>
                        <Link
                          href={`/estoque/${v.slug}`}
                          target="_blank"
                          className="flex items-center gap-1 text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
                        >
                          <ExternalLink className="h-3 w-3" />
                          Ver
                        </Link>
                      </div>
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
          <p className="col-span-2 py-8 text-center text-sm text-zinc-400">
            Nenhum veículo cadastrado.
          </p>
        ) : (
          vehicles.map((v) => (
            <Link
              key={v.id}
              href={`/admin/veiculos/${v.id}`}
              className="flex gap-3 rounded-xl border border-zinc-200 bg-white p-3 shadow-sm hover:border-facil-orange/30 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-facil-orange/30"
            >
              {v.images[0] ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={v.images[0].url}
                  alt={v.title}
                  className="h-16 w-20 shrink-0 rounded-lg object-cover"
                />
              ) : (
                <div className="flex h-16 w-20 shrink-0 items-center justify-center rounded-lg bg-zinc-100 text-zinc-300 dark:bg-zinc-800">
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">{v.title}</p>
                <p className="text-xs text-zinc-400 dark:text-zinc-500">{v.brand.name}</p>
                <div className="mt-1.5 flex items-center justify-between">
                  <StatusBadge status={v.status} />
                  <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                    {v.priceCash != null
                      ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                      : "—"}
                  </span>
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
