"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, useEffect } from "react";

type HeaderProps = {
  siteName?: string;
  whatsappNumber?: string;
};

const nav = [
  { href: "/estoque", label: "Estoque" },
  { href: "/financiamento", label: "Financiamento" },
  { href: "/vender-seu-veiculo", label: "Vender" },
  { href: "/quem-somos", label: "Quem somos" },
  { href: "/blog", label: "Blog" },
  { href: "/contato", label: "Contato" },
];

const WA_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
  </svg>
);

export function Header({ siteName = "FácilCar", whatsappNumber }: HeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  const wa = whatsappNumber?.replace(/\D/g, "") ?? "";
  const whatsappUrl = wa ? `https://wa.me/${wa}` : "#";

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = menuOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [menuOpen]);

  return (
    <>
      <header
        className={`sticky top-0 z-50 border-b border-zinc-800/60 transition-shadow duration-300 glass ${
          scrolled ? "shadow-2xl shadow-black/40" : "shadow-none"
        }`}
      >
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
          {/* Logo */}
          <Link
            href="/"
            className="flex shrink-0 items-center gap-2"
            onClick={() => setMenuOpen(false)}
          >
            <Image
              src="/facilcar-logo.jpg"
              alt={siteName}
              width={34}
              height={34}
              className="rounded-md border border-facil-orange/40 object-cover"
              priority
            />
            <span className="hidden font-bold text-base tracking-tight text-white sm:block">
              {siteName}
            </span>
          </Link>

          {/* Desktop nav — visible at xl (1280px) */}
          <nav className="hidden items-center gap-0 text-xs font-medium text-zinc-300 xl:flex">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="rounded-md px-2 py-1.5 transition hover:bg-white/10 hover:text-white"
              >
                {item.label}
              </Link>
            ))}
          </nav>

          {/* Desktop CTAs — visible at xl */}
          <div className="hidden items-center gap-2 xl:flex">
            <Link
              href="/financiamento"
              className="rounded-lg bg-facil-orange px-3.5 py-1.5 text-xs font-semibold text-white shadow transition hover:bg-facil-orange-hover"
            >
              Simular
            </Link>
            {wa && (
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-green-500/50 bg-green-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-green-700"
              >
                {WA_ICON}
                WhatsApp
              </a>
            )}
          </div>

          {/* Compact CTAs — visible between md and xl */}
          <div className="hidden items-center gap-2 md:flex xl:hidden">
            <Link
              href="/financiamento"
              className="rounded-lg bg-facil-orange px-3 py-1.5 text-xs font-semibold text-white shadow transition hover:bg-facil-orange-hover"
            >
              Simular
            </Link>
            {wa && (
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-600 text-white transition hover:bg-green-700"
                aria-label="WhatsApp"
              >
                {WA_ICON}
              </a>
            )}
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-700 text-zinc-300 transition hover:border-zinc-500 hover:text-white"
              aria-label={menuOpen ? "Fechar menu" : "Abrir menu"}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                <path d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>

          {/* Mobile CTAs — visible below md */}
          <div className="flex items-center gap-2 md:hidden">
            {wa && (
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-600 text-white transition hover:bg-green-700"
                aria-label="WhatsApp"
              >
                {WA_ICON}
              </a>
            )}
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-700 text-zinc-300 transition hover:border-zinc-500 hover:text-white"
              aria-label={menuOpen ? "Fechar menu" : "Abrir menu"}
              aria-expanded={menuOpen}
            >
              {menuOpen ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                  <path d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile/tablet menu overlay */}
      <div
        className={`fixed inset-0 z-40 transition-all duration-300 xl:hidden ${
          menuOpen ? "visible opacity-100" : "invisible opacity-0"
        }`}
        aria-hidden={!menuOpen}
      >
        <div
          className="absolute inset-0 bg-black/70 backdrop-blur-sm"
          onClick={() => setMenuOpen(false)}
        />
        <nav
          className={`absolute right-0 top-0 h-full w-72 bg-zinc-950 shadow-2xl transition-transform duration-300 ease-out ${
            menuOpen ? "translate-x-0" : "translate-x-full"
          }`}
        >
          <div className="flex h-14 items-center justify-between border-b border-zinc-800 px-4">
            <span className="font-bold text-white">{siteName}</span>
            <button
              type="button"
              onClick={() => setMenuOpen(false)}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-zinc-400 transition hover:text-white"
              aria-label="Fechar menu"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="flex flex-col gap-1 p-4">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMenuOpen(false)}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-zinc-200 transition hover:bg-white/10 hover:text-white"
              >
                {item.label}
              </Link>
            ))}
            <div className="mt-4 space-y-2 border-t border-zinc-800 pt-4">
              <Link
                href="/financiamento"
                onClick={() => setMenuOpen(false)}
                className="flex w-full items-center justify-center rounded-lg bg-facil-orange py-2.5 text-sm font-bold text-white transition hover:bg-facil-orange-hover"
              >
                Simular Financiamento
              </Link>
              {wa && (
                <a
                  href={whatsappUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-green-600 py-2.5 text-sm font-semibold text-green-400 transition hover:bg-green-950"
                >
                  {WA_ICON}
                  WhatsApp
                </a>
              )}
            </div>
          </div>
        </nav>
      </div>
    </>
  );
}
