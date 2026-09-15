import { cn } from "@/lib/cn";
import {
  formatPublicPrice,
  publicVehiclePrice,
} from "@/features/catalog/lib/public-price";

type Props = {
  priceCash?: unknown;
  priceRetailAsIs?: unknown;
  size?: "card" | "detail";
  compact?: boolean;
  className?: string;
};

export function PublicVehiclePrice({
  priceCash,
  priceRetailAsIs,
  size = "card",
  compact = false,
  className,
}: Props) {
  const price = publicVehiclePrice({ priceCash, priceRetailAsIs });
  const currentSize =
    size === "detail"
      ? "text-3xl text-facil-orange md:text-4xl"
      : compact
        ? "text-xl text-zinc-950 dark:text-zinc-50"
        : "text-2xl text-zinc-950 dark:text-zinc-50";

  if (price.current == null) {
    return (
      <p
        className={cn(
          "font-black text-zinc-950 dark:text-zinc-50",
          currentSize,
          className,
        )}
      >
        {size === "detail" ? "Consultar valor" : "Consultar"}
      </p>
    );
  }

  if (!price.compare || price.original == null) {
    return (
      <p
        className={cn("font-black tracking-tight", currentSize, className)}
      >
        {formatPublicPrice(price.current)}
      </p>
    );
  }

  const originalLabel = formatPublicPrice(price.original);
  const currentLabel = formatPublicPrice(price.current);

  return (
    <p
      className={cn(
        "flex min-w-0 flex-col gap-0.5",
        size === "detail" ? "gap-1" : null,
        className,
      )}
    >
      <span
        className={cn(
          "inline-flex items-baseline gap-1.5 text-zinc-500",
          size === "detail" ? "text-base md:text-lg" : "text-sm",
        )}
      >
        de
        <s
          className={cn(
            "relative inline-block font-semibold text-zinc-600 no-underline",
            size === "detail" ? "text-lg md:text-xl" : compact ? "text-sm" : "text-base",
          )}
        >
          {originalLabel}
          <svg
            aria-hidden
            className="pointer-events-none absolute inset-0 h-full w-[108%] -translate-x-[4%] overflow-visible"
            viewBox="0 0 100 24"
            preserveAspectRatio="none"
          >
            <line
              x1="2"
              y1="20"
              x2="98"
              y2="4"
              stroke="#dc2626"
              strokeWidth="1.75"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        </s>
      </span>
      <span
        className={cn("font-black tracking-tight", currentSize)}
      >
        <span
          className={cn(
            "mr-1.5 font-semibold",
            size === "detail" ? "text-base text-facil-orange/80 md:text-lg" : "text-sm",
          )}
        >
          por
        </span>
        {currentLabel}
      </span>
    </p>
  );
}
