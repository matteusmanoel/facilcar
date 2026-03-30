"use client";

import Image from "next/image";
import { useState } from "react";

const PLACEHOLDER_SRC = "/no-image.svg";

function isInvalidImageUrl(url: string | null | undefined): boolean {
  if (!url || !url.trim()) return true;
  const u = url.trim();
  return u.startsWith("/mock/") || u === PLACEHOLDER_SRC;
}

type Props = {
  src: string | null | undefined;
  alt: string;
  className?: string;
  sizes?: string;
  priority?: boolean;
};

export function VehicleImage({
  src,
  alt,
  className,
  sizes = "(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw",
  priority = false,
}: Props) {
  const [useFallback, setUseFallback] = useState(() => isInvalidImageUrl(src));
  const showPlaceholder = useFallback || isInvalidImageUrl(src);

  const handleError = () => setUseFallback(true);

  if (showPlaceholder) {
    return (
      <div
        className={`flex min-h-0 min-w-0 items-center justify-center bg-zinc-100 ${className ?? ""}`}
        aria-hidden
      >
        <img
          src={PLACEHOLDER_SRC}
          alt=""
          className="h-20 w-20 max-h-[5rem] max-w-[5rem] object-contain opacity-40"
          style={{ filter: "grayscale(1)" }}
        />
      </div>
    );
  }

  return (
    <Image
      src={src!}
      alt={alt}
      fill
      sizes={sizes}
      className={className}
      onError={handleError}
      priority={priority}
    />
  );
}
