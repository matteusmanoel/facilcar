import { getPageBySlug } from "@/features/content/server/queries";
import { getSiteSettings } from "@/features/settings/server/queries";
import Link from "next/link";
import { notFound } from "next/navigation";

export async function generateMetadata() {
  const page = await getPageBySlug("quem-somos");
  return {
    title: page?.metaTitle ?? page?.title ?? "Quem somos",
    description: page?.metaDescription ?? page?.excerpt ?? undefined,
  };
}

export default async function QuemSomosPage() {
  const [page, settings] = await Promise.all([
    getPageBySlug("quem-somos"),
    getSiteSettings(),
  ]);
  if (!page) notFound();

  const wa = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";

  return (
    <main className="min-h-screen">
      <section className="bg-facil-black px-4 py-16 text-white">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="text-4xl font-extrabold md:text-5xl">{page.title}</h1>
          {page.excerpt && (
            <p className="mt-6 text-lg text-zinc-300">{page.excerpt}</p>
          )}
        </div>
      </section>
      <section className="mx-auto max-w-3xl px-4 py-12">
        <div className="prose prose-zinc max-w-none whitespace-pre-wrap text-facil-muted leading-relaxed">
          {page.body}
        </div>
        <div className="mt-12 rounded-2xl border border-facil-orange/30 bg-orange-50/50 p-8 text-center">
          <p className="font-bold text-zinc-900">Quer nos conhecer pessoalmente?</p>
          <p className="mt-2 text-sm text-facil-muted">
            Agende uma visita ou fale pelo WhatsApp.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-4">
            <Link
              href="/contato"
              className="rounded-xl bg-facil-orange px-6 py-3 font-bold text-white hover:bg-facil-orange-hover"
            >
              Contato
            </Link>
            {wa && (
              <a
                href={`https://wa.me/${wa}`}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-xl border-2 border-facil-orange px-6 py-3 font-bold text-facil-orange hover:bg-facil-orange hover:text-white"
              >
                WhatsApp
              </a>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
