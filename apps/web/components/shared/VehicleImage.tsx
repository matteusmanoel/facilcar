"use client";

import Image from "next/image";
import { useState } from "react";
import { cn } from "@/lib/cn";
import {
  VEHICLE_PLACEHOLDER_SRC,
  isDirectVehicleImageUrl,
  isInvalidVehicleImageUrl,
} from "@/features/vehicle/lib/vehicle-image-src";

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
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const trimmed = src?.trim() ?? "";
  const failed = failedSrc === trimmed;
  const showPlaceholder = failed || isInvalidVehicleImageUrl(trimmed);
  const direct = !showPlaceholder && isDirectVehicleImageUrl(trimmed);

  if (direct) {
    return (
      // Storage URLs skip the image optimizer; a load error still falls back to the placeholder.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={trimmed}
        alt={alt}
        className={cn("absolute inset-0", className)}
        onError={() => setFailedSrc(trimmed)}
        loading={priority ? "eager" : "lazy"}
        fetchPriority={priority ? "high" : "auto"}
      />
    );
  }

  return (
    <Image
      src={showPlaceholder ? VEHICLE_PLACEHOLDER_SRC : trimmed}
      alt={showPlaceholder ? "" : alt}
      fill
      sizes={sizes}
      className={className}
      onError={() => setFailedSrc(trimmed)}
      priority={priority}
    />
  );
}
