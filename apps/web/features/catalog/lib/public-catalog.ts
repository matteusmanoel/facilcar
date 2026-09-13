import type { FuelType, Transmission, VehicleBodyStyle, VehicleType } from "@prisma/client";

export const PUBLIC_CATALOG_PAGE_SIZE = 12;

export const BODY_STYLE_FILTERS = [
  { value: "SEDAN", label: "Sedan" },
  { value: "HATCH", label: "Hatch" },
  { value: "SUV", label: "SUV" },
] as const;

export type CatalogFilters = {
  q?: string;
  brand?: string;
  type?: VehicleType;
  bodyStyle?: VehicleBodyStyle;
  fuelType?: FuelType;
  transmission?: Transmission;
  priceMin?: number;
  priceMax?: number;
  yearMin?: number;
  yearMax?: number;
  sort?: "priceAsc" | "priceDesc" | "yearDesc" | "mileageAsc" | "newest" | "relevance";
  page?: number;
};

export function hasActiveCatalogFilters(filters: Pick<
  CatalogFilters,
  | "q"
  | "brand"
  | "type"
  | "bodyStyle"
  | "fuelType"
  | "transmission"
  | "priceMin"
  | "priceMax"
  | "yearMin"
  | "yearMax"
  | "sort"
>) {
  return Boolean(
    filters.q?.trim() ||
      filters.brand ||
      filters.type ||
      filters.bodyStyle ||
      filters.fuelType ||
      filters.transmission ||
      filters.priceMin != null ||
      filters.priceMax != null ||
      filters.yearMin != null ||
      filters.yearMax != null ||
      (filters.sort && filters.sort !== "newest"),
  );
}

export function parseBodyStyleParam(value: string | undefined): VehicleBodyStyle | undefined {
  if (value === "SEDAN" || value === "HATCH" || value === "SUV") return value;
  return undefined;
}

export function buildPublicCatalogWhere(filters: CatalogFilters) {
  const where: {
    status: "PUBLISHED";
    brand?: { slug: string };
    type?: VehicleType;
    bodyStyle?: VehicleBodyStyle;
    fuelType?: FuelType;
    transmission?: Transmission;
    priceCash?: { gte?: number; lte?: number };
    yearModel?: { gte?: number; lte?: number };
    OR?: Array<{
      title?: { contains: string; mode: "insensitive" };
      model?: { contains: string; mode: "insensitive" };
      brand?: { name: { contains: string; mode: "insensitive" } };
    }>;
  } = {
    status: "PUBLISHED",
  };

  if (filters.brand) where.brand = { slug: filters.brand };
  if (filters.type) where.type = filters.type;
  if (filters.bodyStyle) where.bodyStyle = filters.bodyStyle;
  if (filters.fuelType) where.fuelType = filters.fuelType;
  if (filters.transmission) where.transmission = filters.transmission;
  if (filters.priceMin != null || filters.priceMax != null) {
    where.priceCash = {};
    if (filters.priceMin != null) where.priceCash.gte = filters.priceMin;
    if (filters.priceMax != null) where.priceCash.lte = filters.priceMax;
  }
  if (filters.yearMin != null || filters.yearMax != null) {
    where.yearModel = {};
    if (filters.yearMin != null) where.yearModel.gte = filters.yearMin;
    if (filters.yearMax != null) where.yearModel.lte = filters.yearMax;
  }
  if (filters.q?.trim()) {
    const q = filters.q.trim();
    where.OR = [
      { title: { contains: q, mode: "insensitive" } },
      { model: { contains: q, mode: "insensitive" } },
      { brand: { name: { contains: q, mode: "insensitive" } } },
    ];
  }
  return where;
}

export function toPublicVehicleCard(v: {
  id: string;
  slug: string;
  title: string;
  model: string;
  version: string | null;
  priceCash: unknown;
  yearManufacture: number | null;
  yearModel: number | null;
  mileage: number | null;
  fuelType: string | null;
  transmission: string | null;
  bodyStyle: string | null;
  inspectionResult: string | null;
  brand: { name: string; logoUrl?: string | null };
  images: { url: string }[];
}) {
  return {
    id: v.id,
    slug: v.slug,
    title: v.title,
    model: v.model,
    version: v.version,
    priceCash: v.priceCash != null ? Number(v.priceCash) : null,
    yearManufacture: v.yearManufacture,
    yearModel: v.yearModel,
    mileage: v.mileage,
    fuelType: v.fuelType,
    transmission: v.transmission,
    bodyStyle: v.bodyStyle,
    inspectionResult: v.inspectionResult,
    brand: { name: v.brand.name, logoUrl: v.brand.logoUrl ?? null },
    images: v.images.map((img) => ({ url: img.url })),
  };
}
