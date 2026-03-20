"use client";

import { useState } from "react";

const PLACEHOLDER_SRC = "/no-image.svg";

/** URLs que não devem ser carregadas (mocks locais inexistentes). */
function isInvalidImageUrl(url: string | null | undefined): boolean {
  if (!url || !url.trim()) return true;
  const u = url.trim();
  return u.startsWith("/mock/") || u === PLACEHOLDER_SRC;
}

type Props = {
  src: string | null | undefined;
  alt: string;
  className?: string;
};

export function VehicleImage({ src, alt, className }: Props) {
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

  return <img src={src!} alt={alt} className={className} onError={handleError} />;
}
