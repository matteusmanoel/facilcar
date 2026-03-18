import Link from "next/link";
import { listAdminPages } from "@/features/content/server/queries";

export default async function AdminPaginasPage() {
  const pages = await listAdminPages();

  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold">Páginas</h1>
      <div className="mt-4 overflow-x-auto rounded border">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50">
            <tr>
              <th className="p-2 text-left">Slug</th>
              <th className="p-2 text-left">Título</th>
              <th className="p-2 text-left">Status</th>
              <th className="p-2 text-left">Ações</th>
            </tr>
          </thead>
          <tbody>
            {pages.map((p) => (
              <tr key={p.id} className="border-t">
                <td className="p-2 font-mono text-zinc-600">{p.slug}</td>
                <td className="p-2">{p.title}</td>
                <td className="p-2">{p.status}</td>
                <td className="p-2">
                  <Link href={`/admin/paginas/${p.id}`} className="text-zinc-600 hover:underline">
                    Editar
                  </Link>
                  {" · "}
                  <Link href={`/${p.slug}`} target="_blank" className="text-zinc-600 hover:underline">
                    Ver
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages.length === 0 && (
        <p className="mt-4 text-zinc-500">Nenhuma página. Rode o seed para criar páginas iniciais.</p>
      )}
    </main>
  );
}
