import { getPageBySlug } from "@/features/content/server/queries";
import { notFound } from "next/navigation";

export default async function PoliticaPrivacidadePage() {
  const page = await getPageBySlug("politica-de-privacidade");
  if (!page) notFound();

  return (
    <main className="min-h-screen py-12 px-4">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-semibold">{page.title}</h1>
        <div className="mt-6 prose prose-zinc max-w-none whitespace-pre-wrap">
          {page.body}
        </div>
      </div>
    </main>
  );
}
