import Link from "next/link";
import { notFound } from "next/navigation";
import { getPageById } from "@/features/content/server/queries";
import { PageForm } from "../PageForm";

export default async function AdminPaginaEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const page = await getPageById(id);
  if (!page) notFound();

  return (
    <main className="p-6">
      <Link href="/admin/paginas" className="text-sm text-zinc-600 hover:underline">
        ← Voltar
      </Link>
      <h1 className="mt-4 text-2xl font-semibold">Editar: {page.title}</h1>
      <PageForm page={page} />
    </main>
  );
}
