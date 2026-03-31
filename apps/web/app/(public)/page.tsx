import Link from "next/link";
import { VehicleImage } from "@/components/shared/VehicleImage";
import { ScrollReveal } from "@/components/motion/ScrollReveal";
import { getSiteSettings } from "@/features/settings/server/queries";
import { getFeaturedVehicles } from "@/features/vehicle/server/queries";
import { listPublishedBlogPosts } from "@/features/content/server/queries";
import { BRAND } from "@/lib/brand";
import { fuelLabels, transLabels } from "@/features/vehicle/lib/labels";

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

const benefits = [
  {
    title: "Análise Rápida",
    desc: "CPF, renda e entrada: preencha em 2 minutos e receba proposta de crédito pelo WhatsApp.",
    icon: (
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
        <path d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    title: "Curadoria real",
    desc: "Estoque pensado para quem quer qualidade e preço justo, sem surpresa na hora de fechar.",
    icon: (
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
        <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    title: "Um time pra tudo",
    desc: "Compra, venda, troca e financiamento — você fala com quem entende do negócio.",
    icon: (
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
        <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
      </svg>
    ),
  },
];

const stats = [
  {
    n: "500+",
    label: "Negociações realizadas",
    desc: "Experiência no varejo automotivo.",
  },
  {
    n: "10+",
    label: "Financeiras parceiras",
    desc: "Análise do melhor cenário pra você.",
  },
  {
    n: "100%",
    label: "Financiamento Online",
    desc: "Simule do celular, sem sair de casa.",
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
    settings?.heroTitle ?? "Financie seu próximo carro hoje. 100% online.";
  const heroSubtitle =
    settings?.heroSubtitle ??
    "Seminovos selecionados com financiamento facilitado. Simule agora, receba resposta pelo WhatsApp em minutos.";

  return (
    <main>
      {/* ── HERO ─────────────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-facil-black px-4 pb-20 pt-20 text-white">
        {/* Background texture */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              "repeating-linear-gradient(0deg,transparent,transparent 39px,rgba(255,255,255,.4) 40px),repeating-linear-gradient(90deg,transparent,transparent 39px,rgba(255,255,255,.4) 40px)",
          }}
        />
        {/* Glow orbs */}
        <div className="pointer-events-none absolute -right-16 -top-16 h-72 w-72 rounded-full bg-facil-orange/20 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 left-1/3 h-56 w-56 rounded-full bg-facil-orange/10 blur-3xl" />

        <div className="relative mx-auto max-w-6xl">
          {/* Pill */}
          <div className="flex justify-center">
            <span className="inline-flex items-center gap-2 rounded-full border border-facil-orange/30 bg-facil-orange/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-facil-orange">
              <span className="h-1.5 w-1.5 rounded-full bg-facil-orange animate-pulse" />
              {BRAND.tagline}
            </span>
          </div>

          {/* Headline */}
          <h1 className="font-display mt-6 text-center text-5xl leading-none text-white md:text-7xl lg:text-8xl">
            {heroTitle}
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-center text-lg text-zinc-400 md:text-xl">
            {heroSubtitle}
          </p>

          {/* CTAs */}
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/financiamento"
              className="inline-flex items-center gap-2 rounded-xl bg-facil-orange px-8 py-3.5 text-base font-bold text-white shadow-lg shadow-facil-orange/30 transition hover:bg-facil-orange-hover hover:shadow-facil-orange/50 hover:-translate-y-0.5"
            >
              Simular Financiamento Grátis
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                aria-hidden
              >
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </Link>
            <Link
              href="/estoque"
              className="inline-flex items-center gap-2 rounded-xl border-2 border-white/20 bg-white/5 px-8 py-3.5 text-base font-semibold text-white backdrop-blur transition hover:bg-white/10 hover:border-white/40"
            >
              Ver Estoque
            </Link>
          </div>

          {/* Search bar */}
          <form
            action="/estoque"
            method="get"
            className="mx-auto mt-10 flex max-w-xl flex-col gap-2 sm:flex-row"
          >
            <input
              type="search"
              name="q"
              placeholder="Busque por modelo, marca..."
              className="flex-1 rounded-xl border border-white/15 bg-white/8 px-4 py-3 text-white placeholder:text-zinc-500 focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/40 transition"
            />
            <button
              type="submit"
              className="rounded-xl bg-white px-6 py-3 font-semibold text-facil-black transition hover:bg-zinc-100"
            >
              Buscar
            </button>
          </form>

          {/* Quick stats strip */}
          <div className="mx-auto mt-14 grid max-w-2xl grid-cols-3 divide-x divide-white/10 rounded-2xl border border-white/10 bg-white/5 backdrop-blur">
            {stats.map((s) => (
              <div key={s.n} className="px-4 py-4 text-center">
                <p className="font-display text-3xl text-facil-orange md:text-4xl">
                  {s.n}
                </p>
                <p className="mt-0.5 text-xs font-semibold uppercase tracking-wide text-zinc-400">
                  {s.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FEATURED VEHICLES ────────────────────────────────── */}
      {featured.length > 0 && (
        <section className="py-20 px-4">
          <div className="mx-auto max-w-6xl">
            <ScrollReveal>
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-facil-orange">
                    Seleção especial
                  </p>
                  <h2 className="mt-1 text-3xl font-bold text-zinc-900 md:text-4xl">
                    Destaques do estoque
                  </h2>
                  <p className="mt-2 text-facil-muted">
                    Veículos em destaque — disponibilidade sujeita à
                    confirmação.
                  </p>
                </div>
                <Link
                  href="/estoque"
                  className="shrink-0 font-semibold text-facil-orange hover:underline"
                >
                  Ver todos →
                </Link>
              </div>
            </ScrollReveal>

            <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {featured.map((v, i) => {
                const fuel = v.fuelType
                  ? (fuelLabels[v.fuelType] ?? v.fuelType)
                  : null;
                const trans = v.transmission
                  ? (transLabels[v.transmission] ?? v.transmission)
                  : null;
                return (
                  <ScrollReveal key={v.id} delay={i * 80}>
                    <Link
                      href={`/estoque/${v.slug}`}
                      className="vehicle-card group block"
                    >
                      <div className="relative aspect-[16/10] overflow-hidden bg-zinc-100">
                        <VehicleImage
                          src={v.images[0]?.url}
                          alt={v.title}
                          className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                          priority={i === 0}
                        />
                        <span className="absolute left-3 top-3 badge-orange">
                          Destaque
                        </span>
                        {v.yearModel && (
                          <span className="absolute right-3 top-3 badge-zinc">
                            {v.yearModel}
                          </span>
                        )}
                      </div>
                      <div className="p-4">
                        <h3 className="font-bold text-white line-clamp-2 group-hover:text-facil-orange transition-colors">
                          {v.title}
                        </h3>
                        <p className="mt-2 text-xl font-extrabold text-facil-orange">
                          {v.priceCash != null
                            ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                            : "Consultar"}
                        </p>
                        {(fuel || trans || v.mileage != null) && (
                          <div className="mt-3 flex flex-wrap gap-1.5">
                            {v.mileage != null && (
                              <span className="badge-zinc">
                                {v.mileage.toLocaleString("pt-BR")} km
                              </span>
                            )}
                            {fuel && <span className="badge-zinc">{fuel}</span>}
                            {trans && (
                              <span className="badge-zinc">{trans}</span>
                            )}
                          </div>
                        )}
                        <p className="mt-3 text-xs font-semibold text-facil-orange">
                          Simular financiamento →
                        </p>
                      </div>
                    </Link>
                  </ScrollReveal>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* ── BENEFITS ─────────────────────────────────────────── */}
      <section className="border-y border-facil-border bg-facil-surface py-20 px-4">
        <div className="mx-auto max-w-6xl">
          <ScrollReveal>
            <h2 className="text-center text-3xl font-bold text-zinc-900 md:text-4xl">
              Por que escolher a FácilCar?
            </h2>
          </ScrollReveal>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {benefits.map((b, i) => (
              <ScrollReveal key={b.title} delay={i * 100}>
                <div className="group rounded-2xl border border-facil-border bg-white p-8 transition-all duration-300 hover:border-facil-orange/40 hover:shadow-lg hover:-translate-y-0.5">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-facil-orange-light text-facil-orange transition-colors group-hover:bg-facil-orange group-hover:text-white">
                    {b.icon}
                  </div>
                  <h3 className="mt-5 text-xl font-bold text-zinc-900">
                    {b.title}
                  </h3>
                  <p className="mt-3 text-facil-muted leading-relaxed">
                    {b.desc}
                  </p>
                </div>
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
              Muito além da venda de carros
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
                  Solicitar análise →
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

      {/* ── TESTIMONIALS ─────────────────────────────────────── */}
      <section className="py-20 px-4">
        <div className="mx-auto max-w-6xl">
          <ScrollReveal>
            <p className="text-center text-xs font-semibold uppercase tracking-widest text-facil-orange">
              Depoimentos
            </p>
            <h2 className="mt-2 text-center text-3xl font-bold text-zinc-900 md:text-4xl">
              O que nossos clientes dizem
            </h2>
          </ScrollReveal>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {testimonials.map((t, i) => (
              <ScrollReveal key={t.name} delay={i * 80}>
                <blockquote className="flex h-full flex-col rounded-2xl border border-facil-border bg-white p-6 shadow-sm transition hover:border-facil-orange/30 hover:shadow-md">
                  {/* Stars */}
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
                  <p className="mt-4 flex-1 text-zinc-600 leading-relaxed">
                    &ldquo;{t.text}&rdquo;
                  </p>
                  <footer className="mt-5 flex items-center gap-3 border-t border-zinc-100 pt-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-facil-orange text-sm font-bold text-white">
                      {t.initials}
                    </div>
                    <div>
                      <cite className="not-italic text-sm font-bold text-zinc-900">
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

      {/* ── ABOUT ────────────────────────────────────────────── */}
      <section className="border-t border-facil-border bg-facil-surface py-20 px-4">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-10 lg:flex-row lg:justify-between">
          <ScrollReveal
            direction="left"
            className="max-w-xl text-center lg:text-left"
          >
            <p className="text-xs font-semibold uppercase tracking-widest text-facil-orange">
              Sobre nós
            </p>
            <h2 className="mt-2 text-3xl font-bold text-zinc-900 md:text-4xl">
              Conheça a FácilCar
            </h2>
            <p className="mt-4 text-facil-muted leading-relaxed">
              Somos uma multimarcas focada em experiência: atendimento humano,
              estoque variado e compromisso com transparência em cada etapa.
            </p>
            <Link
              href="/quem-somos"
              className="mt-6 inline-flex items-center gap-2 font-bold text-facil-orange hover:underline"
            >
              Saiba mais sobre nós →
            </Link>
          </ScrollReveal>
          {settings?.instagramUrl && (
            <ScrollReveal direction="right">
              <a
                href={settings.instagramUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-3 rounded-2xl bg-facil-orange px-8 py-4 font-bold text-white shadow-lg shadow-facil-orange/25 transition hover:bg-facil-orange-hover hover:-translate-y-0.5"
              >
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden
                >
                  <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
                </svg>
                Siga no Instagram
              </a>
            </ScrollReveal>
          )}
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
                  <h2 className="mt-1 text-3xl font-bold text-zinc-900 md:text-4xl">
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
            <div className="mt-10 grid gap-6 md:grid-cols-3">
              {posts.map((post, i) => (
                <ScrollReveal key={post.id} delay={i * 80}>
                  <Link
                    href={`/blog/${post.slug}`}
                    className="group flex flex-col rounded-2xl border border-facil-border bg-white p-6 shadow-sm transition-all duration-300 hover:border-facil-orange/40 hover:shadow-lg hover:-translate-y-0.5"
                  >
                    <h3 className="font-bold text-zinc-900 group-hover:text-facil-orange transition-colors">
                      {post.title}
                    </h3>
                    {post.excerpt && (
                      <p className="mt-2 flex-1 line-clamp-2 text-sm text-facil-muted">
                        {post.excerpt}
                      </p>
                    )}
                    <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-facil-orange">
                      Ler artigo →
                    </span>
                  </Link>
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
              Fale com a equipe agora — tiramos suas dúvidas e montamos a melhor
              proposta.
            </p>
          </ScrollReveal>
          <ScrollReveal delay={150}>
            <div className="mt-10 flex flex-wrap justify-center gap-4">
              <Link
                href="/contato"
                className="rounded-xl bg-facil-orange px-8 py-3.5 font-bold text-white shadow-lg shadow-facil-orange/30 transition hover:bg-facil-orange-hover hover:-translate-y-0.5"
              >
                Formulário de contato
              </Link>
              {wa && (
                <a
                  href={whatsappHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-xl border-2 border-white/20 px-8 py-3.5 font-bold text-white transition hover:bg-white/10 hover:border-white/40"
                >
                  WhatsApp
                </a>
              )}
            </div>
          </ScrollReveal>
        </div>
      </section>
    </main>
  );
}
