import Link from "next/link";
import { getSiteSettings } from "@/features/settings/server/queries";
import { getFeaturedVehicles } from "@/features/vehicle/server/queries";

export default async function HomePage() {
  const [settings, featured] = await Promise.all([
    getSiteSettings(),
    getFeaturedVehicles(4),
  ]);

  return (
    <main className="min-h-screen">
      <section className="bg-zinc-50 py-16 px-4">
        <div className="mx-auto max-w-6xl text-center">
          <h1 className="text-3xl font-bold md:text-4xl">
            {settings?.heroTitle ?? "Seu próximo veículo começa aqui"}
          </h1>
          <p className="mt-2 text-lg text-zinc-600">
            {settings?.heroSubtitle ?? "Estoque selecionado, atendimento rápido."}
          </p>
          <Link
            href="/estoque"
            className="mt-6 inline-block rounded-lg bg-zinc-900 px-6 py-3 font-medium text-white hover:bg-zinc-800"
          >
            Ver estoque
          </Link>
        </div>
      </section>

      {featured.length > 0 && (
        <section className="py-12 px-4">
          <div className="mx-auto max-w-6xl">
            <h2 className="text-2xl font-semibold">Destaques</h2>
            <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {featured.map((v) => (
                <Link
                  key={v.id}
                  href={`/estoque/${v.slug}`}
                  className="rounded-lg border bg-white p-4 shadow-sm transition hover:shadow"
                >
                  <div className="aspect-video bg-zinc-200 rounded mb-3">
                    {v.images[0] && (
                      <img
                        src={v.images[0].url}
                        alt=""
                        className="h-full w-full object-cover rounded"
                      />
                    )}
                  </div>
                  <h3 className="font-semibold">{v.title}</h3>
                  <p className="mt-1 text-sm text-zinc-600">
                    {v.priceCash != null
                      ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                      : "Consultar valor"}
                  </p>
                </Link>
              ))}
            </div>
            <Link
              href="/estoque"
              className="mt-6 inline-block text-zinc-600 hover:underline"
            >
              Ver todos →
            </Link>
          </div>
        </section>
      )}

      <section className="border-t py-12 px-4">
        <div className="mx-auto max-w-6xl grid gap-8 md:grid-cols-2">
          <div className="rounded-lg border bg-white p-6">
            <h3 className="text-lg font-semibold">Financiamento</h3>
            <p className="mt-2 text-zinc-600">
              Condições especiais com as melhores taxas do mercado.
            </p>
            <Link href="/financiamento" className="mt-4 inline-block font-medium text-zinc-900 hover:underline">
              Solicitar análise →
            </Link>
          </div>
          <div className="rounded-lg border bg-white p-6">
            <h3 className="text-lg font-semibold">Vender seu veículo</h3>
            <p className="mt-2 text-zinc-600">
              Avaliação rápida e proposta sem compromisso.
            </p>
            <Link href="/vender-seu-veiculo" className="mt-4 inline-block font-medium text-zinc-900 hover:underline">
              Saiba mais →
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
