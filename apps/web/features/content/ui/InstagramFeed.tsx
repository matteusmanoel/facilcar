"use client";

import { useRef } from "react";
import { InstagramIcon } from "@/components/shared/brand-icons";
import { INSTAGRAM_CAROUSEL_POSTS } from "@/features/content/lib/instagram-posts";

type Props = {
  profileUrl: string;
};

function instagramHandle(profileUrl: string) {
  try {
    const path = new URL(profileUrl).pathname.replace(/^\/+|\/+$/g, "");
    const handle = path.split("/")[0];
    return handle ? `@${handle}` : "@facilcarmultimarcas";
  } catch {
    return "@facilcarmultimarcas";
  }
}

export function InstagramFeed({ profileUrl }: Props) {
  const handle = instagramHandle(profileUrl);
  const scrollerRef = useRef<HTMLDivElement>(null);

  function scrollByCard(direction: -1 | 1) {
    const node = scrollerRef.current;
    if (!node) return;
    const amount = Math.min(360, node.clientWidth * 0.85);
    node.scrollBy({ left: direction * amount, behavior: "smooth" });
  }

  return (
    <div className="w-full">
      <div className="text-center">
        <h3 className="text-3xl font-extrabold tracking-tight text-foreground md:text-4xl">
          Siga-nos no Instagram!
        </h3>
        <a
          href={profileUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-flex items-center gap-2 text-lg font-semibold text-facil-orange hover:underline"
        >
          <InstagramIcon className="h-5 w-5" />
          {handle}
        </a>
      </div>

      <div className="relative mt-8 md:px-6">
        <button
          type="button"
          aria-label="Posts anteriores"
          onClick={() => scrollByCard(-1)}
          className="absolute left-0 top-1/2 z-10 hidden h-10 w-10 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-facil-border bg-white text-foreground shadow-md transition hover:border-facil-orange hover:text-facil-orange md:flex"
        >
          <Chevron dir="left" />
        </button>
        <button
          type="button"
          aria-label="Próximos posts"
          onClick={() => scrollByCard(1)}
          className="absolute right-0 top-1/2 z-10 hidden h-10 w-10 translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-facil-border bg-white text-foreground shadow-md transition hover:border-facil-orange hover:text-facil-orange md:flex"
        >
          <Chevron dir="right" />
        </button>

        <div
          ref={scrollerRef}
          className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-2 [scrollbar-width:thin]"
        >
          {INSTAGRAM_CAROUSEL_POSTS.map((shortcode) => (
            <article
              key={shortcode}
              className="relative w-[min(100%,20.5rem)] shrink-0 snap-start overflow-hidden rounded-2xl border border-facil-border bg-white shadow-sm"
            >
              <div className="relative h-[24rem] overflow-hidden">
                <iframe
                  title={`Post ${handle} no Instagram`}
                  src={`https://www.instagram.com/p/${shortcode}/embed`}
                  className="pointer-events-none h-[52rem] w-[calc(100%+2px)] max-w-none -translate-x-px border-0"
                  loading="lazy"
                  allow="encrypted-media; clipboard-write"
                  tabIndex={-1}
                />
              </div>
              <a
                href={`https://www.instagram.com/p/${shortcode}/`}
                target="_blank"
                rel="noopener noreferrer"
                className="absolute inset-0"
                aria-label={`Abrir publicação de ${handle} no Instagram`}
              />
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

function Chevron({ dir }: { dir: "left" | "right" }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden>
      {dir === "left" ? <path d="M15 6l-6 6 6 6" /> : <path d="M9 6l6 6-6 6" />}
    </svg>
  );
}
