"use client";

import { useCallback, useState } from "react";
import { VehicleImage } from "@/components/shared/VehicleImage";

type Img = { id: string; url: string; alt?: string | null };

function ChevronLeft({ className }: { className?: string }) {
  return (
    <svg className={className} width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M15 18l-6-6 6-6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronRight({ className }: { className?: string }) {
  return (
    <svg className={className} width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M9 18l6-6-6-6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function VehicleGallery({ images, title }: { images: Img[]; title: string }) {
  const [active, setActive] = useState(0);
  const count = images.length;

  const goPrev = useCallback(() => {
    setActive((i) => (i === 0 ? count - 1 : i - 1));
  }, [count]);

  const goNext = useCallback(() => {
    setActive((i) => (i === count - 1 ? 0 : i + 1));
  }, [count]);

  if (!count) {
    return (
      <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-100 shadow-sm">
        <div className="relative aspect-[4/3] min-h-[240px] md:min-h-[min(420px,50vh)] md:aspect-[16/10]">
          <VehicleImage src={null} alt={title} className="h-full w-full object-cover" />
        </div>
      </div>
    );
  }

  const main = images[active] ?? images[0];

  return (
    <div className="space-y-4">
      <div className="relative overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-100 shadow-md">
        <div className="relative aspect-[4/3] min-h-[240px] md:min-h-[min(420px,52vh)] md:aspect-[16/10]">
          <VehicleImage
            src={main.url}
            alt={main.alt || title}
            className="h-full w-full object-cover"
          />
          {count > 1 && (
            <>
              <button
                type="button"
                onClick={goPrev}
                className="absolute left-2 top-1/2 z-10 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full border border-zinc-200/80 bg-white/95 text-zinc-700 shadow-md backdrop-blur-sm transition hover:bg-white hover:text-zinc-900 md:left-4 md:h-12 md:w-12"
                aria-label="Foto anterior"
              >
                <ChevronLeft className="h-6 w-6 md:h-7 md:w-7" />
              </button>
              <button
                type="button"
                onClick={goNext}
                className="absolute right-2 top-1/2 z-10 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full border border-zinc-200/80 bg-white/95 text-zinc-700 shadow-md backdrop-blur-sm transition hover:bg-white hover:text-zinc-900 md:right-4 md:h-12 md:w-12"
                aria-label="Próxima foto"
              >
                <ChevronRight className="h-6 w-6 md:h-7 md:w-7" />
              </button>
              <div className="absolute bottom-3 left-1/2 z-10 -translate-x-1/2 rounded-full bg-black/60 px-3 py-1 text-xs font-medium text-white backdrop-blur-sm">
                {active + 1} / {count}
              </div>
            </>
          )}
        </div>
      </div>
      {count > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {images.map((img, i) => (
            <button
              key={img.id}
              type="button"
              onClick={() => setActive(i)}
              className={`h-20 w-28 shrink-0 overflow-hidden rounded-lg border-2 transition md:h-[5.25rem] md:w-32 ${
                i === active
                  ? "border-facil-orange ring-2 ring-facil-orange/35"
                  : "border-transparent opacity-75 hover:opacity-100"
              }`}
            >
              <VehicleImage src={img.url} alt="" className="h-full w-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
