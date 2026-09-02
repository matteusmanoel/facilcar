import Link from "next/link";
import { VehicleImage } from "@/components/shared/VehicleImage";
import { fuelLabels, transLabels } from "@/features/vehicle/lib/labels";
import { cn } from "@/lib/cn";

export type VehicleCardVehicle = {
  id: string;
  slug: string;
  title: string;
  priceCash?: unknown;
  yearModel?: number | null;
  mileage?: number | null;
  fuelType?: string | null;
  transmission?: string | null;
  images?: { url: string }[] | null;
};

type Props = {
  vehicle: VehicleCardVehicle;
  featured?: boolean;
  compact?: boolean;
  headingLevel?: "h2" | "h3";
  footerLabel?: string;
  priority?: boolean;
  className?: string;
};

function formatPrice(priceCash: unknown): string {
  if (priceCash == null) return "Consultar";
  const n = Number(priceCash);
  if (!Number.isFinite(n)) return "Consultar";
  return `R$ ${n.toLocaleString("pt-BR")}`;
}

export function VehicleCard({
  vehicle,
  featured = false,
  compact = false,
  headingLevel = "h2",
  footerLabel,
  priority = false,
  className,
}: Props) {
  const firstImage = Array.isArray(vehicle.images) ? vehicle.images[0] : null;
  const fuel = vehicle.fuelType
    ? (fuelLabels[vehicle.fuelType] ?? vehicle.fuelType)
    : null;
  const trans = vehicle.transmission
    ? (transLabels[vehicle.transmission] ?? vehicle.transmission)
    : null;
  const Heading = headingLevel;

  return (
    <Link href={`/estoque/${vehicle.slug}`} className={cn("vehicle-card group", className)}>
      <div className="relative aspect-[16/10] shrink-0 overflow-hidden bg-facil-surface">
        <VehicleImage
          src={firstImage?.url}
          alt={vehicle.title}
          className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
          priority={priority}
        />
        {featured ? <span className="absolute left-3 top-3 badge-orange">Destaque</span> : null}
        {vehicle.yearModel ? (
          <span className="absolute right-3 top-3 badge-zinc">{vehicle.yearModel}</span>
        ) : null}
      </div>
      <div
        className={cn(
          "flex min-h-0 flex-1 flex-col bg-zinc-50 shadow-inner dark:bg-zinc-900/40",
          compact ? "p-4" : "p-5",
        )}
      >
        <Heading
          className={cn(
            "line-clamp-2 font-bold leading-snug text-zinc-950 transition-colors group-hover:text-facil-orange dark:text-zinc-50",
            compact ? "min-h-10 text-sm" : "min-h-12 text-base",
          )}
        >
          {vehicle.title}
        </Heading>
        <p className={cn("mt-2 font-black text-facil-orange", compact ? "text-xl" : "text-2xl")}>
          {formatPrice(vehicle.priceCash)}
        </p>
        <div className={cn("mt-3 flex min-h-7 flex-wrap content-start gap-1.5", compact && "min-h-6")}>
          {vehicle.mileage != null ? (
            <span className="badge-zinc">{vehicle.mileage.toLocaleString("pt-BR")} km</span>
          ) : null}
          {fuel ? <span className="badge-zinc">{fuel}</span> : null}
          {trans ? <span className="badge-zinc">{trans}</span> : null}
        </div>
        {footerLabel ? (
          <p className="mt-auto pt-3 text-xs font-semibold text-facil-orange">{footerLabel}</p>
        ) : (
          <div className="mt-auto" />
        )}
      </div>
    </Link>
  );
}
