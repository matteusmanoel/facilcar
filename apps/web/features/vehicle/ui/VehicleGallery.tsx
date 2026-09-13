"use client";

import { useCallback, useRef, useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { Dialog, DialogPortal, DialogTitle } from "@/components/ui/dialog";
import { VehicleImage } from "@/components/shared/VehicleImage";
import { wrapGalleryIndex } from "@/features/vehicle/lib/gallery-nav";
import { InspectionSeal } from "@/features/catalog/ui/InspectionSeal";
import { cn } from "@/lib/cn";

type Img = { id: string; url: string; alt?: string | null };

const navBtnClass =
  "flex h-11 w-11 items-center justify-center rounded-full border border-zinc-200/80 bg-white/95 text-zinc-700 shadow-md backdrop-blur-sm transition hover:bg-white hover:text-zinc-900 md:h-12 md:w-12";

export function VehicleGallery({
  images,
  title,
  inspectionResult,
}: {
  images: Img[];
  title: string;
  inspectionResult?: string | null;
}) {
  const [active, setActive] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const touchStartX = useRef<number | null>(null);
  const count = images.length;

  const goPrev = useCallback(() => {
    setActive((i) => wrapGalleryIndex(i, count, -1));
  }, [count]);

  const goNext = useCallback(() => {
    setActive((i) => wrapGalleryIndex(i, count, 1));
  }, [count]);

  const onKeyNav = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        goNext();
      }
    },
    [goPrev, goNext],
  );

  function onTouchStart(e: React.TouchEvent) {
    touchStartX.current = e.changedTouches[0]?.clientX ?? null;
  }

  function onTouchEnd(e: React.TouchEvent) {
    const start = touchStartX.current;
    touchStartX.current = null;
    if (start == null || count < 2) return;
    const dx = (e.changedTouches[0]?.clientX ?? start) - start;
    if (dx > 50) goPrev();
    else if (dx < -50) goNext();
  }

  if (!count) {
    return (
      <div className="w-full overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-100 shadow-sm">
        <div className="relative aspect-[4/3] w-full md:aspect-[16/10]">
          <VehicleImage src={null} alt={title} className="h-full w-full object-cover" />
          <InspectionSeal result={inspectionResult} />
        </div>
      </div>
    );
  }

  const main = images[active] ?? images[0];

  return (
    <div className="w-full space-y-4 overflow-hidden">
      <div className="w-full overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-100 shadow-md">
        <div
          className="relative aspect-[4/3] w-full md:aspect-[16/10]"
          onTouchStart={onTouchStart}
          onTouchEnd={onTouchEnd}
        >
          <VehicleImage
            src={main.url}
            alt={main.alt || title}
            className="h-full w-full object-cover"
            sizes="(max-width: 768px) 100vw, (max-width: 1280px) 60vw, 800px"
            priority
          />
          <InspectionSeal result={inspectionResult} />
          <button
            type="button"
            onClick={() => setLightboxOpen(true)}
            className="absolute inset-0 z-[1] cursor-zoom-in"
            aria-label="Ampliar foto"
          />
          {count > 1 && (
            <>
              <button
                type="button"
                onClick={goPrev}
                className={cn(navBtnClass, "absolute left-2 top-1/2 z-10 -translate-y-1/2 md:left-4")}
                aria-label="Foto anterior"
              >
                <ChevronLeft className="h-6 w-6 md:h-7 md:w-7" />
              </button>
              <button
                type="button"
                onClick={goNext}
                className={cn(navBtnClass, "absolute right-2 top-1/2 z-10 -translate-y-1/2 md:right-4")}
                aria-label="Próxima foto"
              >
                <ChevronRight className="h-6 w-6 md:h-7 md:w-7" />
              </button>
              <div className="pointer-events-none absolute bottom-3 left-1/2 z-10 -translate-x-1/2 rounded-full bg-black/60 px-3 py-1 text-xs font-medium text-white backdrop-blur-sm">
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
              className={`relative h-20 w-28 shrink-0 overflow-hidden rounded-lg border-2 transition md:h-[5.25rem] md:w-32 ${
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

      <Dialog open={lightboxOpen} onOpenChange={setLightboxOpen}>
        <DialogPortal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-[80] bg-black/85 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <DialogPrimitive.Content
            className="fixed inset-0 z-[80] flex items-center justify-center p-4 outline-none"
            onKeyDown={onKeyNav}
            onPointerDown={(e) => {
              if (e.target === e.currentTarget) setLightboxOpen(false);
            }}
            onTouchStart={onTouchStart}
            onTouchEnd={onTouchEnd}
          >
            <DialogTitle className="sr-only">
              {main.alt || title} — foto {active + 1} de {count}
            </DialogTitle>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={main.url}
              alt={main.alt || title}
              className="max-h-[85vh] max-w-[min(92vw,1400px)] object-contain"
            />
            <DialogPrimitive.Close
              className="absolute right-4 top-4 z-10 flex h-11 w-11 items-center justify-center rounded-full bg-white/95 text-zinc-800 transition hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-facil-orange"
              aria-label="Fechar"
            >
              <X className="h-5 w-5" />
            </DialogPrimitive.Close>
            {count > 1 ? (
              <>
                <button
                  type="button"
                  onClick={goPrev}
                  className={cn(navBtnClass, "absolute left-3 top-1/2 z-10 -translate-y-1/2 md:left-6")}
                  aria-label="Foto anterior"
                >
                  <ChevronLeft className="h-6 w-6 md:h-7 md:w-7" />
                </button>
                <button
                  type="button"
                  onClick={goNext}
                  className={cn(navBtnClass, "absolute right-3 top-1/2 z-10 -translate-y-1/2 md:right-6")}
                  aria-label="Próxima foto"
                >
                  <ChevronRight className="h-6 w-6 md:h-7 md:w-7" />
                </button>
                <p className="pointer-events-none absolute bottom-5 left-1/2 -translate-x-1/2 rounded-full bg-black/60 px-3 py-1 text-xs font-medium text-white">
                  {active + 1} / {count}
                </p>
              </>
            ) : null}
          </DialogPrimitive.Content>
        </DialogPortal>
      </Dialog>
    </div>
  );
}
