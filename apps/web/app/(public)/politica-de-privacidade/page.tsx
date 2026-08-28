import { getPageBySlug } from "@/features/content/server/queries";
import { cmsPageMetadata } from "@/features/content/server/page-metadata";
import { notFound } from "next/navigation";

export async function generateMetadata() {
  return cmsPageMetadata("politica-de-privacidade", "Política de privacidade");
}

export default async function PoliticaPrivacidadePage() {
  const page = await getPageBySlug("politica-de-privacidade");
  if (!page) notFound();

  return (
    <main className="min-h-screen py-12 px-4">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-semibold">{page.title}</h1>
        <div className="mt-6 public-prose">
          {page.body}
        </div>
      </div>
    </main>
  );
}
