import Link from "next/link";
import { listAdminPages } from "@/features/content/server/queries";

export default async function AdminPaginasPage() {
  const pages = await listAdminPages();

  return (
    <div className="admin-page admin-section">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Páginas</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">{pages.length} página(s)</p>
      </div>

      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-100 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-800/50">
              <tr>
                <th className="admin-table-header">Slug</th>
                <th className="admin-table-header">Título</th>
                <th className="admin-table-header">Status</th>
                <th className="admin-table-header">Ações</th>
              </tr>
            </thead>
            <tbody>
              {pages.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-10 text-center text-sm text-zinc-400">
                    Nenhuma página. Rode o seed para criar páginas iniciais.
                  </td>
                </tr>
              ) : (
                pages.map((p) => (
                  <tr key={p.id} className="border-t border-zinc-100 hover:bg-zinc-50/50 dark:border-zinc-800 dark:hover:bg-zinc-800/40">
                    <td className="admin-table-cell font-mono text-zinc-500 dark:text-zinc-400">{p.slug}</td>
                    <td className="admin-table-cell font-medium text-zinc-900 dark:text-zinc-100">{p.title}</td>
                    <td className="admin-table-cell">
                      <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${p.status === "PUBLISHED" ? "bg-green-100 text-green-800 dark:bg-green-950/40 dark:text-green-400" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"}`}>
                        {p.status === "PUBLISHED" ? "Publicada" : "Rascunho"}
                      </span>
                    </td>
                    <td className="admin-table-cell">
                      <div className="flex gap-3">
                        <Link href={`/admin/paginas/${p.id}`} className="font-medium text-facil-orange hover:underline">
                          Editar
                        </Link>
                        <Link href={`/${p.slug}`} target="_blank" className="text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300">
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
    </div>
  );
}
