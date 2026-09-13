"use client";

import { useRef } from "react";
import { getImageProps } from "next/image";
import Link from "next/link";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { WhatsAppIcon } from "@/components/shared/brand-icons";

gsap.registerPlugin(useGSAP);

type Props = {
  whatsappHref: string;
};

const stats = [
  { n: "500+", label: "Negociações realizadas" },
  { n: "12+", label: "Financeiras parceiras" },
  { n: "100%", label: "Financiamento Online" },
];

export function HomeHero({ whatsappHref }: Props) {
  const rootRef = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

      const targets = "[data-hero-copy], [data-hero-cta], [data-hero-band]";
      const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
      tl.fromTo(
        "[data-hero-copy]",
        { autoAlpha: 0, y: 32 },
        { autoAlpha: 1, y: 0, duration: 0.8, stagger: 0.12 },
      )
        .fromTo(
          "[data-hero-cta]",
          { autoAlpha: 0, y: 24 },
          { autoAlpha: 1, y: 0, duration: 0.65 },
          "-=0.45",
        )
        .fromTo(
          "[data-hero-band]",
          { autoAlpha: 0, y: 28 },
          { autoAlpha: 1, y: 0, duration: 0.7, stagger: 0.12 },
          "-=0.35",
        );

      const safety = window.setTimeout(() => {
        gsap.set(targets, { autoAlpha: 1, y: 0 });
      }, 2000);
      tl.eventCallback("onComplete", () => window.clearTimeout(safety));
      return () => window.clearTimeout(safety);
    },
    { scope: rootRef },
  );

  const {
    props: { srcSet: desktopSrcSet },
  } = getImageProps({
    alt: "Família recebendo a chave do veículo na FácilCar Multimarcas",
    sizes: "100vw",
    priority: true,
    quality: 75,
    width: 1672,
    height: 941,
    src: "/facilcar-banner-familia.webp",
  });
  const {
    props: { srcSet: mobileSrcSet, src, alt },
  } = getImageProps({
    alt: "Família recebendo a chave do veículo na FácilCar Multimarcas",
    sizes: "100vw",
    priority: true,
    quality: 75,
    width: 851,
    height: 1848,
    src: "/facilcar-banner-familia-mobile.webp",
  });

  return (
    <section ref={rootRef} className="bg-facil-black text-white">
      <div className="relative min-h-[40rem] overflow-hidden max-md:min-h-[calc(100svh-3.5rem)] md:min-h-[44rem] lg:min-h-[48rem]">
        <picture className="absolute inset-0 block h-full w-full">
          <source media="(min-width: 768px)" srcSet={desktopSrcSet} sizes="100vw" />
          <img
            alt={alt}
            src={src}
            srcSet={mobileSrcSet}
            sizes="100vw"
            decoding="async"
            fetchPriority="high"
            className="absolute inset-0 h-full w-full object-cover object-[center_30%] md:object-[center_right]"
          />
        </picture>
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_top,rgba(0,0,0,0.72)_0%,rgba(0,0,0,0.28)_22%,transparent_42%)] md:bg-[linear-gradient(90deg,rgba(0,0,0,0.78)_0%,rgba(0,0,0,0.48)_22%,rgba(0,0,0,0.16)_42%,transparent_62%)]" />
        <div className="pointer-events-none absolute inset-x-0 top-0 h-44 bg-gradient-to-b from-black/75 via-black/40 to-transparent md:hidden" />

        <div className="relative flex min-h-[40rem] flex-col items-stretch justify-end pb-8 pt-16 max-md:min-h-[calc(100svh-3.5rem)] sm:pb-12 md:min-h-[44rem] md:items-start md:justify-center md:py-24 lg:min-h-[48rem]">
          <p
            data-hero-copy
            className="font-hero absolute inset-x-0 top-3 z-10 px-5 text-center text-[0.95rem] font-bold leading-snug tracking-tight text-[#FF8A33] [text-shadow:0_1px_3px_rgba(0,0,0,0.95),0_10px_28px_rgba(0,0,0,0.75)] md:static md:inset-auto md:top-auto md:max-w-xl md:px-0 md:pl-8 md:text-left md:text-2xl md:font-semibold lg:max-w-2xl lg:pl-10 lg:text-[1.75rem]"
          >
            Aqui, cada chave entregue tem uma história...
          </p>
          <div className="font-hero relative w-full px-3 sm:max-w-lg sm:px-6 md:max-w-xl md:pl-8 lg:max-w-2xl lg:pl-10">
            <div className="pointer-events-none absolute inset-x-0 -bottom-8 -top-16 bg-gradient-to-t from-black/75 via-black/35 to-transparent md:hidden" />
            <h1
              data-hero-copy
              className="relative mt-1.5 text-[1.7rem] font-extrabold leading-[1.06] tracking-tight text-white [text-shadow:0_2px_4px_rgba(0,0,0,0.85),0_10px_28px_rgba(0,0,0,0.55)] sm:mt-4 sm:text-5xl md:text-6xl lg:text-[4.35rem]"
            >
              A próxima pode <br /> ser a{" "}
              <span className="text-[#FF8A33] [text-shadow:0_2px_4px_rgba(0,0,0,0.85),0_8px_20px_rgba(0,0,0,0.5)]">sua</span>
            </h1>
            {whatsappHref !== "#" ? (
              <a
                data-hero-cta
                href={whatsappHref}
                target="_blank"
                rel="noopener noreferrer"
                className="group relative mt-5 inline-flex w-full min-h-14 items-center justify-center gap-2 overflow-hidden rounded-full bg-[#25D366] px-3 py-3.5 text-base font-extrabold tracking-tight text-white whitespace-nowrap shadow-[0_10px_28px_rgba(37,211,102,0.45),0_2px_0_rgba(255,255,255,0.25)_inset] ring-2 ring-white/30 transition duration-300 hover:-translate-y-0.5 hover:bg-[#1EBE57] hover:shadow-[0_16px_40px_rgba(37,211,102,0.55)] hover:ring-white/45 sm:mt-9 sm:min-h-0 sm:w-auto sm:gap-3 sm:px-8 sm:py-4 sm:text-lg sm:tracking-normal"
              >
                <span className="pointer-events-none absolute inset-0 bg-gradient-to-b from-white/25 to-transparent" />
                <WhatsAppIcon className="relative h-6 w-6 shrink-0 sm:h-6 sm:w-6" />
                <span className="relative min-w-0">Quero começar minha história</span>
                <svg
                  className="hero-cta-chevron relative h-5 w-5 shrink-0"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  aria-hidden
                >
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </a>
            ) : null}
          </div>
        </div>
      </div>

      <div
        className="relative overflow-hidden border-t border-white/10"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg,transparent,transparent 39px,rgba(255,255,255,.04) 40px),repeating-linear-gradient(90deg,transparent,transparent 39px,rgba(255,255,255,.04) 40px)",
        }}
      >
        <div className="pointer-events-none absolute bottom-0 left-1/3 h-56 w-56 rounded-full bg-facil-orange/10 blur-3xl" />

        <div
          data-hero-band
          className="grid w-full grid-cols-3 divide-x divide-white/10 border-b border-white/10 bg-white/5"
        >
          {stats.map((s) => (
            <div key={s.n} className="px-3 py-5 text-center sm:px-6 sm:py-7">
              <p className="font-display text-3xl text-facil-orange sm:text-4xl md:text-5xl">{s.n}</p>
              <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-400 sm:text-xs">
                {s.label}
              </p>
            </div>
          ))}
        </div>

        <div data-hero-band className="relative px-4 py-10 sm:px-6 sm:py-12">
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/financiamento"
              className="inline-flex items-center gap-2 rounded-xl bg-facil-orange px-8 py-3.5 text-base font-bold text-white shadow-lg shadow-facil-orange/30 transition hover:-translate-y-0.5 hover:bg-facil-orange-hover hover:shadow-facil-orange/50"
            >
              Quero simular!
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
              className="inline-flex items-center justify-center gap-2 rounded-xl border-2 border-white/20 bg-white/5 px-8 py-3.5 text-base font-semibold text-white backdrop-blur transition hover:border-white/40 hover:bg-white/10"
            >
              Ver estoque
            </Link>
          </div>

          <form action="/estoque" method="get" className="mx-auto mt-10 flex max-w-xl flex-col gap-2 sm:flex-row">
            <input
              type="search"
              name="q"
              placeholder="Busque por modelo, marca..."
              className="flex-1 rounded-xl border border-white/15 bg-white/8 px-4 py-3 text-white placeholder:text-zinc-500 transition focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/40"
            />
            <button
              type="submit"
              className="rounded-xl bg-white px-6 py-3 font-semibold text-facil-black transition hover:bg-facil-surface"
            >
              Buscar
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}
