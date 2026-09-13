import Link from "next/link";
import { ScrollReveal } from "@/components/motion/ScrollReveal";
import { getSiteSettings } from "@/features/settings/server/queries";
import { getFeaturedVehicles } from "@/features/vehicle/server/queries";
import { listPublishedBlogPosts } from "@/features/content/server/queries";
import { FeaturedVehiclesCarousel } from "@/features/catalog/ui/FeaturedVehiclesCarousel";
import { HomeHero } from "@/features/catalog/ui/HomeHero";
import { catalogFullBleedClass } from "@/features/catalog/lib/shell";
import { BlogCard } from "@/features/content/ui/BlogCard";
import { InstagramFeed } from "@/features/content/ui/InstagramFeed";
import { STORE_MAPS_EMBED_SRC, STORE_MAPS_PLACE_URL } from "@/lib/store-maps";

const testimonials = [
  {
    name: "Carlos M.",
    role: "Empresário",
    initials: "CM",
    text: "Atendimento direto, sem enrolação. Fechei meu SUV em um dia.",
  },
  {
    name: "Juliana R.",
    role: "Autônoma",
    initials: "JR",
    text: "Financiamento claro e carro revisado. Recomendo a FácilCar.",
  },
  {
    name: "Roberto A.",
    role: "Motorista de app",
    initials: "RA",
    text: "Troquei o usado e saí de carro novo pra mim. Processo tranquilo.",
  },
];

export default async function HomePage() {
  const [settings, featured, posts] = await Promise.all([
    getSiteSettings(),
    getFeaturedVehicles(9),
    listPublishedBlogPosts(3),
  ]);

  const wa = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";
  const whatsappHref = wa
    ? `https://wa.me/${wa}?text=${encodeURIComponent("Olá! Vim pelo site da FácilCar.")}`
    : "#";
  const heroWhatsappHref = wa
    ? `https://wa.me/${wa}?text=${encodeURIComponent("Olá! Quero começar minha história na FácilCar.")}`
    : "#";
  const mapsHref = settings?.googleMapsUrl?.trim() || STORE_MAPS_PLACE_URL;
  const addressLine =
    [
      settings?.addressLine,
      [settings?.city, settings?.state].filter(Boolean).join(" / "),
      settings?.zipCode,
    ]
      .filter(Boolean)
      .join(" · ") || "R. Ipanema, 1206 — Periolo · Cascavel / PR";

  return (
    <main>
      <HomeHero whatsappHref={heroWhatsappHref} />

      {featured.length > 0 && (
        <section data-whatsapp-reveal className="py-16 sm:py-20">
          <div className={catalogFullBleedClass}>
            <ScrollReveal>
              <div className="text-center">
                <p className="text-xs font-semibold uppercase tracking-widest text-facil-orange">
                  Seleção especial
                </p>
                <h2 className="mt-1 text-3xl font-bold text-foreground md:text-4xl">
                  Destaques do estoque
                </h2>
              </div>
            </ScrollReveal>

            <div className="mt-10">
              <FeaturedVehiclesCarousel vehicles={featured} />
            </div>

            <div className="mt-10 flex justify-center">
              <Link
                href="/estoque"
                className="inline-flex w-full items-center justify-center rounded-full bg-facil-orange px-8 py-3.5 text-base font-bold text-white shadow-lg shadow-facil-orange/35 transition hover:-translate-y-0.5 hover:bg-facil-orange-hover sm:w-auto"
              >
                Veja todas as novidades
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* ── TESTIMONIALS ─────────────────────────────────────── */}
      <section
        {...(featured.length === 0 ? { "data-whatsapp-reveal": "" } : {})}
        className="border-y border-facil-border bg-facil-surface py-20 px-4"
      >
        <div className="mx-auto max-w-6xl">
          <ScrollReveal>
            <p className="text-center text-xs font-semibold uppercase tracking-widest text-facil-orange">
              Depoimentos
            </p>
            <h2 className="mt-2 text-center text-3xl font-bold text-foreground md:text-4xl">
              O que nossos clientes dizem
            </h2>
          </ScrollReveal>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {testimonials.map((t, i) => (
              <ScrollReveal key={t.name} delay={i * 80}>
                <blockquote className="flex h-full flex-col rounded-2xl border border-facil-border bg-facil-card p-6 shadow-sm transition hover:border-facil-orange/30 hover:shadow-md">
                  <div className="flex gap-0.5 text-amber-400">
                    {Array.from({ length: 5 }).map((_, j) => (
                      <svg
                        key={j}
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                        aria-hidden
                      >
                        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                      </svg>
                    ))}
                  </div>
                  <p className="mt-4 flex-1 text-facil-muted leading-relaxed">
                    &ldquo;{t.text}&rdquo;
                  </p>
                  <footer className="mt-5 flex items-center gap-3 border-t border-facil-border pt-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-facil-orange text-sm font-bold text-white">
                      {t.initials}
                    </div>
                    <div>
                      <cite className="not-italic text-sm font-bold text-foreground">
                        {t.name}
                      </cite>
                      <p className="text-xs text-facil-muted">{t.role}</p>
                    </div>
                  </footer>
                </blockquote>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINANCING & SELL ──────────────────────────────────── */}
      <section className="bg-facil-black py-20 px-4 text-white">
        <div className="mx-auto max-w-6xl">
          <ScrollReveal>
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-facil-orange">
              Serviços
            </p>
            <h2 className="text-3xl font-bold md:text-4xl">
            Condições sob medida 
            </h2>
          </ScrollReveal>
          <div className="mt-10 grid gap-6 lg:grid-cols-2">
            <ScrollReveal direction="left">
              <div className="group h-full rounded-2xl border border-white/10 bg-white/5 p-8 transition hover:border-facil-orange/40 hover:bg-white/8">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-facil-orange/15 text-facil-orange">
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    aria-hidden
                  >
                    <rect x="2" y="5" width="20" height="14" rx="2" />
                    <path d="M2 10h20" />
                  </svg>
                </div>
                <h3 className="mt-5 text-2xl font-bold">Financiamento</h3>
                <p className="mt-3 text-zinc-400 leading-relaxed">
                  Simulação e análise com as principais financeiras. Entenda
                  prazo, parcela e documentação em poucos passos.
                </p>
                <Link
                  href="/financiamento"
                  className="mt-6 inline-flex items-center gap-2 rounded-lg bg-facil-orange px-6 py-3 font-semibold transition hover:bg-facil-orange-hover"
                >
                  Quero simular!
                </Link>
              </div>
            </ScrollReveal>
            <ScrollReveal direction="right">
              <div className="group h-full rounded-2xl border border-white/10 bg-white/5 p-8 transition hover:border-facil-orange/40 hover:bg-white/8">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-facil-orange/15 text-facil-orange">
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    aria-hidden
                  >
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                  </svg>
                </div>
                <h3 className="mt-5 text-2xl font-bold">Venda e consignação</h3>
                <p className="mt-3 text-zinc-400 leading-relaxed">
                  Quer vender com segurança? Avaliamos seu carro e cuidamos da
                  divulgação e da negociação pra você.
                </p>
                <Link
                  href="/vender-seu-veiculo"
                  className="mt-6 inline-flex items-center gap-2 rounded-lg border-2 border-facil-orange px-6 py-3 font-semibold text-facil-orange transition hover:bg-facil-orange hover:text-white"
                >
                  Quero avaliar meu carro →
                </Link>
              </div>
            </ScrollReveal>
          </div>
        </div>
      </section>

      {/* ── LOCATION ────────────────────────────────────────── */}
      <section className="border-t border-facil-border bg-facil-surface py-20 px-4">
        <div className="mx-auto max-w-5xl">
          <ScrollReveal>
            <p className="text-center text-xs font-semibold uppercase tracking-widest text-facil-orange">
              Onde estamos
            </p>
            <h2 className="mt-2 text-center text-3xl font-bold text-foreground md:text-4xl">
              Venha nos visitar
            </h2>
            <p className="mt-3 text-center text-sm text-facil-muted">{addressLine}</p>
          </ScrollReveal>
          <ScrollReveal delay={80}>
            <div className="mt-8 overflow-hidden rounded-2xl border border-facil-border bg-facil-card shadow-sm">
              <iframe
                title="Mapa da FácilCar Multimarcas no Google Maps"
                src={STORE_MAPS_EMBED_SRC}
                className="aspect-[4/3] w-full border-0 md:aspect-[16/9]"
                loading="lazy"
                allowFullScreen
                referrerPolicy="no-referrer-when-downgrade"
              />
            </div>
            <p className="mt-4 text-center">
              <a
                href={mapsHref}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-facil-orange hover:underline"
              >
                Abrir no Google Maps
              </a>
            </p>
          </ScrollReveal>
          {settings?.instagramUrl ? (
            <ScrollReveal className="mt-14" delay={80}>
              <InstagramFeed profileUrl={settings.instagramUrl} />
            </ScrollReveal>
          ) : null}
        </div>
      </section>

      {/* ── BLOG ─────────────────────────────────────────────── */}
      {posts.length > 0 && (
        <section className="py-20 px-4">
          <div className="mx-auto max-w-6xl">
            <ScrollReveal>
              <div className="flex items-end justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-facil-orange">
                    Conteúdo
                  </p>
                  <h2 className="mt-1 text-3xl font-bold text-foreground md:text-4xl">
                    Blog
                  </h2>
                </div>
                <Link
                  href="/blog"
                  className="shrink-0 font-semibold text-facil-orange hover:underline"
                >
                  Ver todos →
                </Link>
              </div>
            </ScrollReveal>
            <div className="mt-10 grid items-stretch gap-3 sm:gap-4 md:grid-cols-3">
              {posts.map((post, i) => (
                <ScrollReveal key={post.id} delay={i * 80} className="h-full">
                  <BlogCard post={post} headingLevel="h3" />
                </ScrollReveal>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── FINAL CTA ────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-facil-black py-20 px-4 text-center text-white">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              "repeating-linear-gradient(45deg,transparent,transparent 39px,rgba(255,255,255,.4) 40px)",
          }}
        />
        <div className="pointer-events-none absolute left-1/4 top-0 h-64 w-64 -translate-y-1/2 rounded-full bg-facil-orange/20 blur-3xl" />
        <div className="relative">
          <ScrollReveal>
            <p className="text-xs font-semibold uppercase tracking-widest text-facil-orange">
              Próximo passo
            </p>
            <h2 className="font-display mt-3 text-4xl text-white md:text-6xl">
              Pronto pra dar o próximo passo?
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-zinc-400">
              Fale com a gente agora, tire suas dúvidas e descubra a melhor proposta para você.
            </p>
          </ScrollReveal>
          <ScrollReveal delay={150}>
            <div className="mt-10 flex flex-wrap justify-center gap-4">
              {wa && (
                <a
                  href={whatsappHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-xl bg-facil-orange px-8 py-3.5 font-bold text-white shadow-lg shadow-facil-orange/30 transition hover:bg-facil-orange-hover hover:-translate-y-0.5"
                >
                  Falar com quem entende
                </a>
              )}
              <Link
                href="/estoque"
                className="rounded-xl border-2 border-white/20 px-8 py-3.5 font-bold text-white transition hover:bg-white/10 hover:border-white/40"
              >
                Ver estoque
              </Link>
            </div>
          </ScrollReveal>
        </div>
      </section>
    </main>
  );
}
