import Link from "next/link";
import { VehicleImage } from "@/components/shared/VehicleImage";
import { InspectionSeal } from "@/features/catalog/ui/InspectionSeal";
import { PublicVehiclePrice } from "@/features/catalog/ui/PublicVehiclePrice";
import { bodyStyleLabels } from "@/features/vehicle/lib/labels";
import { cn } from "@/lib/cn";

export type VehicleCardVehicle = {
  id: string;
  slug: string;
  title: string;
  model?: string | null;
  version?: string | null;
  priceCash?: unknown;
  priceRetailAsIs?: unknown;
  yearManufacture?: number | null;
  yearModel?: number | null;
  mileage?: number | null;
  fuelType?: string | null;
  transmission?: string | null;
  bodyStyle?: string | null;
  inspectionResult?: string | null;
  brand?: { name: string; logoUrl?: string | null } | string | null;
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

function brandName(brand: VehicleCardVehicle["brand"]): string | null {
  if (!brand) return null;
  if (typeof brand === "string") return brand;
  return brand.name || null;
}

function yearLabel(vehicle: VehicleCardVehicle): string | null {
  if (vehicle.yearManufacture && vehicle.yearModel) {
    if (vehicle.yearManufacture === vehicle.yearModel) return String(vehicle.yearModel);
    return `${vehicle.yearManufacture}/${vehicle.yearModel}`;
  }
  return vehicle.yearModel ? String(vehicle.yearModel) : vehicle.yearManufacture ? String(vehicle.yearManufacture) : null;
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
  const Heading = headingLevel;
  const brand = brandName(vehicle.brand);
  const years = yearLabel(vehicle);
  const bodyLabel = vehicle.bodyStyle ? (bodyStyleLabels[vehicle.bodyStyle] ?? vehicle.bodyStyle) : null;
  const heading = brand ? `${brand} ${vehicle.model || vehicle.title}` : vehicle.title;
  const subtitle =
    vehicle.version?.trim() ||
    (brand ? vehicle.title : null);

  return (
    <Link href={`/estoque/${vehicle.slug}`} className={cn("vehicle-card group", className)}>
      <div className={cn("relative shrink-0 overflow-hidden bg-facil-surface", compact ? "aspect-[16/10]" : "aspect-[4/3]")}>
        <VehicleImage
          src={firstImage?.url}
          alt={vehicle.title}
          className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
          priority={priority}
        />
        {featured ? <span className="absolute left-3 top-3 z-10 badge-orange">Destaque</span> : null}
        <InspectionSeal result={vehicle.inspectionResult} />
        {bodyLabel ? (
          <span className="absolute bottom-3 left-3 z-10 rounded-full bg-white/95 px-2.5 py-0.5 text-xs font-semibold text-zinc-700 shadow-sm">
            {bodyLabel}
          </span>
        ) : null}
      </div>
      <div
        className={cn(
          "flex min-h-0 flex-1 flex-col bg-white dark:bg-zinc-900/40",
          compact ? "p-4" : "p-5",
        )}
      >
        <Heading
          className={cn(
            "line-clamp-2 font-bold leading-snug text-zinc-950 transition-colors group-hover:text-facil-orange dark:text-zinc-50",
            compact ? "text-sm" : "text-lg",
          )}
        >
          {heading}
        </Heading>
        {subtitle && subtitle !== heading ? (
          <p className="mt-1 line-clamp-1 text-sm text-facil-muted">{subtitle}</p>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-facil-muted">
          {years ? <span>{years}</span> : null}
          {vehicle.mileage != null ? <span>{vehicle.mileage.toLocaleString("pt-BR")} km</span> : null}
        </div>
        <div className="mt-auto flex items-end justify-between gap-3 pt-4">
          <PublicVehiclePrice
            priceCash={vehicle.priceCash}
            priceRetailAsIs={vehicle.priceRetailAsIs}
            compact={compact}
          />
          <span className="shrink-0 rounded-lg border border-zinc-200 px-3 py-1.5 text-sm font-medium text-zinc-700 transition group-hover:border-facil-orange group-hover:text-facil-orange dark:border-zinc-700 dark:text-zinc-200">
            {footerLabel ?? "Ver mais"}
          </span>
        </div>
      </div>
    </Link>
  );
}
