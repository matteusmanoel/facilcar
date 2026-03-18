import Link from "next/link";
import { listAdminBlogPosts } from "@/features/content/server/queries";

export default async function AdminBlogPage() {
  const posts = await listAdminBlogPosts();

  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold">Blog</h1>
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
            {posts.map((p) => (
              <tr key={p.id} className="border-t">
                <td className="p-2 font-mono text-zinc-600">{p.slug}</td>
                <td className="p-2">{p.title}</td>
                <td className="p-2">{p.status}</td>
                <td className="p-2">
                  <Link href={`/admin/blog/${p.id}`} className="text-zinc-600 hover:underline">
                    Editar
                  </Link>
                  {" · "}
                  {p.status === "PUBLISHED" && (
                    <>
                      <Link href={`/blog/${p.slug}`} target="_blank" className="text-zinc-600 hover:underline">
                        Ver
                      </Link>
                      {" · "}
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {posts.length === 0 && (
        <p className="mt-4 text-zinc-500">Nenhum post. Rode o seed para criar posts iniciais.</p>
      )}
    </main>
  );
}
