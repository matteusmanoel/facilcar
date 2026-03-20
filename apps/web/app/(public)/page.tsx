import Link from "next/link";
import { VehicleImage } from "@/components/shared/VehicleImage";
import { getSiteSettings } from "@/features/settings/server/queries";
import { getFeaturedVehicles } from "@/features/vehicle/server/queries";
import { listPublishedBlogPosts } from "@/features/content/server/queries";
import { BRAND } from "@/lib/brand";

const testimonials = [
  {
    name: "Carlos M.",
    role: "Empresário",
    text: "Atendimento direto, sem enrolação. Fechei meu SUV em um dia.",
  },
  {
    name: "Juliana R.",
    role: "Autônoma",
    text: "Financiamento claro e carro revisado. Recomendo a FácilCar.",
  },
  {
    name: "Roberto A.",
    role: "Motorista de app",
    text: "Troquei o usado e saí de carro novo pra mim. Processo tranquilo.",
  },
];

export default async function HomePage() {
  const [settings, featured, posts] = await Promise.all([
    getSiteSettings(),
    getFeaturedVehicles(4),
    listPublishedBlogPosts(3),
  ]);

  const wa = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";
  const whatsappHref = wa
    ? `https://wa.me/${wa}?text=${encodeURIComponent("Olá! Vim pelo site da FácilCar.")}`
    : "#";

  const heroTitle =
    settings?.heroTitle ?? "Seu próximo carro, do jeito mais fácil.";
  const heroSubtitle =
    settings?.heroSubtitle ??
    "Seminovos selecionados, financiamento com especialistas e avaliação justa do seu usado — tudo em um só lugar.";

  return (
    <main>
      <section className="relative overflow-hidden bg-gradient-to-br from-facil-black via-zinc-900 to-facil-black px-4 py-20 text-white">
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-facil-orange/20 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 left-1/4 h-48 w-48 rounded-full bg-facil-orange/10 blur-3xl" />
        <div className="relative mx-auto max-w-6xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-facil-orange">
            {BRAND.tagline}
          </p>
          <h1 className="mt-4 text-4xl font-extrabold leading-tight tracking-tight md:text-5xl lg:text-6xl">
            {heroTitle}
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-zinc-300 md:text-xl">
            {heroSubtitle}
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/estoque"
              className="inline-flex rounded-xl bg-facil-orange px-8 py-3.5 text-base font-bold text-white shadow-lg shadow-facil-orange/25 transition hover:bg-facil-orange-hover"
            >
              Ver estoque completo
            </Link>
            {wa && (
              <a
                href={whatsappHref}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex rounded-xl border-2 border-white/30 bg-white/5 px-8 py-3.5 text-base font-semibold text-white backdrop-blur transition hover:bg-white/10"
              >
                Falar no WhatsApp
              </a>
            )}
          </div>
          <form
            action="/estoque"
            method="get"
            className="mx-auto mt-12 flex max-w-xl flex-col gap-2 sm:flex-row"
          >
            <input
              type="search"
              name="q"
              placeholder="Busque por modelo, marca..."
              className="flex-1 rounded-xl border border-white/20 bg-white/10 px-4 py-3 text-white placeholder:text-zinc-400 focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/50"
            />
            <button
              type="submit"
              className="rounded-xl bg-white px-6 py-3 font-semibold text-facil-black hover:bg-zinc-100"
            >
              Buscar
            </button>
          </form>
        </div>
      </section>

      {featured.length > 0 && (
        <section className="py-16 px-4">
          <div className="mx-auto max-w-6xl">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div>
                <h2 className="text-3xl font-bold text-zinc-900">Destaques</h2>
                <p className="mt-2 text-facil-muted">
                  Veículos em destaque no estoque — disponibilidade sujeita à confirmação.
                </p>
              </div>
              <Link
                href="/estoque"
                className="font-semibold text-facil-orange hover:underline"
              >
                Ver todos →
              </Link>
            </div>
            <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {featured.map((v) => (
                <Link
                  key={v.id}
                  href={`/estoque/${v.slug}`}
                  className="group overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm transition hover:border-facil-orange/40 hover:shadow-xl"
                >
                  <div className="relative aspect-[16/10] overflow-hidden bg-zinc-100">
                    <VehicleImage
                      src={v.images[0]?.url}
                      alt={v.title}
                      className="h-full w-full object-cover transition group-hover:scale-105"
                    />
                    <span className="absolute left-3 top-3 rounded-full bg-facil-orange px-2.5 py-0.5 text-xs font-bold text-white">
                      Destaque
                    </span>
                  </div>
                  <div className="p-4">
                    <h3 className="font-bold text-zinc-900 line-clamp-2">{v.title}</h3>
                    <p className="mt-2 text-xl font-extrabold text-facil-orange">
                      {v.priceCash != null
                        ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                        : "Consultar"}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="border-y border-zinc-200 bg-white py-14 px-4">
        <div className="mx-auto grid max-w-6xl gap-8 sm:grid-cols-3">
          {[
            { n: "500+", l: "Negociações realizadas", d: "Experiência no varejo automotivo." },
            { n: "10+", l: "Financeiras parceiras", d: "Análise do melhor cenário pra você." },
            { n: "100%", l: "Transparência", d: "Documentação e condições claras desde o primeiro contato." },
          ].map((s) => (
            <div key={s.l} className="text-center">
              <p className="text-4xl font-black text-facil-orange">{s.n}</p>
              <p className="mt-2 font-bold text-zinc-900">{s.l}</p>
              <p className="mt-1 text-sm text-facil-muted">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="py-16 px-4">
        <div className="mx-auto max-w-6xl">
          <h2 className="text-center text-3xl font-bold text-zinc-900">
            Por que escolher a FácilCar?
          </h2>
          <div className="mt-12 grid gap-8 md:grid-cols-3">
            {[
              {
                t: "Curadoria real",
                d: "Estoque pensado para quem quer qualidade e preço justo, sem surpresa na hora de fechar.",
              },
              {
                t: "Um time pra tudo",
                d: "Compra, venda, troca e financiamento — você fala com quem entende do negócio.",
              },
              {
                t: "Agilidade",
                d: "Resposta rápida no WhatsApp e processo enxuto, do interesse à proposta.",
              },
            ].map((b) => (
              <div
                key={b.t}
                className="rounded-2xl border border-zinc-200 bg-zinc-50 p-8 transition hover:border-facil-orange/30"
              >
                <div className="mb-4 h-1 w-12 rounded-full bg-facil-orange" />
                <h3 className="text-xl font-bold text-zinc-900">{b.t}</h3>
                <p className="mt-3 text-facil-muted leading-relaxed">{b.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-facil-black py-16 px-4 text-white">
        <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
            <h3 className="text-2xl font-bold">Financiamento</h3>
            <p className="mt-3 text-zinc-300">
              Simulação e análise com as principais financeiras. Entenda prazo, parcela e documentação
              em poucos passos.
            </p>
            <Link
              href="/financiamento"
              className="mt-6 inline-flex rounded-lg bg-facil-orange px-6 py-3 font-semibold hover:bg-facil-orange-hover"
            >
              Solicitar análise →
            </Link>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-8">
            <h3 className="text-2xl font-bold">Venda e consignação</h3>
            <p className="mt-3 text-zinc-300">
              Quer vender com segurança? Avaliamos seu carro e cuidamos da divulgação e da negociação
              pra você.
            </p>
            <Link
              href="/vender-seu-veiculo"
              className="mt-6 inline-flex rounded-lg border-2 border-facil-orange px-6 py-3 font-semibold text-facil-orange hover:bg-facil-orange hover:text-white"
            >
              Quero avaliar meu carro →
            </Link>
          </div>
        </div>
      </section>

      <section className="py-16 px-4">
        <div className="mx-auto max-w-6xl">
          <h2 className="text-center text-3xl font-bold text-zinc-900">
            O que nossos clientes dizem
          </h2>
          <div className="mt-12 grid gap-8 md:grid-cols-3">
            {testimonials.map((t) => (
              <blockquote
                key={t.name}
                className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm"
              >
                <p className="text-facil-muted leading-relaxed">&ldquo;{t.text}&rdquo;</p>
                <footer className="mt-4 border-t border-zinc-100 pt-4">
                  <cite className="not-italic font-bold text-zinc-900">{t.name}</cite>
                  <p className="text-sm text-facil-muted">{t.role}</p>
                </footer>
              </blockquote>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-zinc-200 bg-zinc-50 py-16 px-4">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-xl text-center lg:text-left">
            <h2 className="text-3xl font-bold text-zinc-900">Conheça a FácilCar</h2>
            <p className="mt-4 text-facil-muted leading-relaxed">
              Somos uma multimarcas focada em experiência: atendimento humano, estoque variado e
              compromisso com transparência em cada etapa.
            </p>
            <Link
              href="/quem-somos"
              className="mt-6 inline-block font-bold text-facil-orange hover:underline"
            >
              Saiba mais sobre nós →
            </Link>
          </div>
          {settings?.instagramUrl && (
            <a
              href={settings.instagramUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-2xl bg-facil-orange px-8 py-4 font-bold text-white hover:bg-facil-orange-hover"
            >
              Siga no Instagram
            </a>
          )}
        </div>
      </section>

      {posts.length > 0 && (
        <section className="py-16 px-4">
          <div className="mx-auto max-w-6xl">
            <div className="flex items-end justify-between gap-4">
              <h2 className="text-3xl font-bold text-zinc-900">Blog</h2>
              <Link href="/blog" className="font-semibold text-facil-orange hover:underline">
                Ver todos →
              </Link>
            </div>
            <div className="mt-10 grid gap-8 md:grid-cols-3">
              {posts.map((post) => (
                <Link
                  key={post.id}
                  href={`/blog/${post.slug}`}
                  className="group rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition hover:border-facil-orange/40"
                >
                  <h3 className="font-bold text-zinc-900 group-hover:text-facil-orange">
                    {post.title}
                  </h3>
                  {post.excerpt && (
                    <p className="mt-2 line-clamp-2 text-sm text-facil-muted">{post.excerpt}</p>
                  )}
                  <span className="mt-4 inline-block text-sm font-semibold text-facil-orange">
                    Ler artigo →
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="bg-gradient-to-r from-facil-orange to-orange-600 py-14 px-4 text-center text-white">
        <h2 className="text-2xl font-bold md:text-3xl">Pronto pra dar o próximo passo?</h2>
        <p className="mx-auto mt-3 max-w-lg text-white/90">
          Fale com a equipe agora — tiramos suas dúvidas e montamos a melhor proposta.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-4">
          <Link
            href="/contato"
            className="rounded-xl bg-white px-8 py-3 font-bold text-facil-orange hover:bg-zinc-100"
          >
            Formulário de contato
          </Link>
          {wa && (
            <a
              href={whatsappHref}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl border-2 border-white px-8 py-3 font-bold text-white hover:bg-white/10"
            >
              WhatsApp
            </a>
          )}
        </div>
      </section>
    </main>
  );
}
