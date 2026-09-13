"use client";

import Image from "next/image";
import { useState } from "react";

const PLACEHOLDER_SRC = "/vehicle-placeholder.webp";
const LEGACY_PLACEHOLDER = "/no-image.svg";

function isInvalidImageUrl(url: string | null | undefined): boolean {
  if (!url || !url.trim()) return true;
  const u = url.trim();
  return u.startsWith("/mock/") || u === PLACEHOLDER_SRC || u === LEGACY_PLACEHOLDER;
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

  return (
    <Image
      src={showPlaceholder ? PLACEHOLDER_SRC : src!}
      alt={showPlaceholder ? "" : alt}
      fill
      sizes={sizes}
      className={className}
      onError={() => setUseFallback(true)}
      priority={priority}
    />
  );
}
