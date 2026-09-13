"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { WhatsAppIcon } from "@/components/shared/brand-icons";
import { COOKIE_BANNER_OFFSET_CLASS } from "@/lib/cookie-consent";

type Props = {
  whatsappNumber?: string | null;
  message?: string;
};

function findRevealTarget() {
  return (
    document.querySelector("[data-hero-cta]") ??
    document.querySelector("[data-whatsapp-reveal]")
  );
}

export function WhatsAppFloat({
  whatsappNumber,
  message = "Olá! Vim pelo site da FácilCar.",
}: Props) {
  const pathname = usePathname();
  const gatedToReveal = pathname === "/";
  const [revealed, setRevealed] = useState(!gatedToReveal);

  const wa = whatsappNumber?.replace(/\D/g, "") ?? "";

  useEffect(() => {
    if (!gatedToReveal) {
      setRevealed(true);
      return;
    }

    let io: IntersectionObserver | null = null;
    let mo: MutationObserver | null = null;

    const observe = (target: Element) => {
      const hideWhileInView = target.matches("[data-hero-cta]");
      const sync = (entry: IntersectionObserverEntry) => {
        if (hideWhileInView) {
          setRevealed(!entry.isIntersecting && entry.boundingClientRect.top < 0);
          return;
        }
        setRevealed(entry.isIntersecting || entry.boundingClientRect.top < 0);
      };

      io = new IntersectionObserver(([entry]) => sync(entry), { threshold: 0 });
      io.observe(target);

      const rect = target.getBoundingClientRect();
      const intersecting = rect.bottom > 0 && rect.top < window.innerHeight;
      sync({
        isIntersecting: intersecting,
        boundingClientRect: rect,
      } as IntersectionObserverEntry);
    };

    const existing = findRevealTarget();
    if (existing) {
      observe(existing);
    } else {
      mo = new MutationObserver(() => {
        const el = findRevealTarget();
        if (!el) return;
        mo?.disconnect();
        observe(el);
      });
      mo.observe(document.body, { childList: true, subtree: true });
    }

    return () => {
      io?.disconnect();
      mo?.disconnect();
    };
  }, [gatedToReveal]);

  if (!wa) return null;

  const href = `https://wa.me/${wa}?text=${encodeURIComponent(message)}`;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Fale no WhatsApp"
      aria-hidden={!revealed}
      tabIndex={revealed ? 0 : -1}
      className={`group fixed right-5 z-50 flex items-center gap-2 rounded-full bg-green-500 shadow-lg shadow-green-500/40 transition-all duration-300 hover:-translate-y-0.5 hover:bg-green-600 hover:shadow-green-500/60 hover:pr-5 ${COOKIE_BANNER_OFFSET_CLASS} ${
        revealed
          ? "translate-y-0 opacity-100"
          : "pointer-events-none translate-y-3 opacity-0"
      }`}
    >
      {revealed ? (
        <span className="absolute inset-0 rounded-full bg-green-400 opacity-30 animate-ping" />
      ) : null}
      <span className="relative z-10 flex h-[72px] w-[72px] shrink-0 items-center justify-center">
        <WhatsAppIcon className="h-9 w-9 text-white" />
      </span>
      <span className="max-w-0 overflow-hidden whitespace-nowrap text-sm font-semibold text-white opacity-0 transition-all duration-300 group-hover:max-w-[180px] group-hover:opacity-100">
        Fale no WhatsApp
      </span>
    </a>
  );
}
