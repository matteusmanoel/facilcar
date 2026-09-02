import { getPageBySlug } from "@/features/content/server/queries";
import { cmsPageMetadata } from "@/features/content/server/page-metadata";
import { notFound } from "next/navigation";

export async function generateMetadata() {
  return cmsPageMetadata("termos-de-uso", "Termos de uso");
}

export default async function TermosUsoPage() {
  const page = await getPageBySlug("termos-de-uso");
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
