import { prisma } from "@/lib/db";
import type { FuelType, Transmission, VehicleType } from "@prisma/client";

const PAGE_SIZE = 12;

export type CatalogFilters = {
  q?: string;
  brand?: string;
  type?: VehicleType;
  fuelType?: FuelType;
  transmission?: Transmission;
  priceMin?: number;
  priceMax?: number;
  yearMin?: number;
  yearMax?: number;
  sort?: "priceAsc" | "priceDesc" | "yearDesc" | "mileageAsc" | "newest" | "relevance";
  page?: number;
};

export async function listPublicVehicles(filters: CatalogFilters = {}) {
  const page = Math.max(1, filters.page ?? 1);
  const skip = (page - 1) * PAGE_SIZE;

  const where: {
    status: "PUBLISHED";
    brand?: { slug: string };
    type?: VehicleType;
    fuelType?: FuelType;
    transmission?: Transmission;
    priceCash?: { gte?: number; lte?: number };
    yearModel?: { gte?: number; lte?: number };
    OR?: Array<{ title?: { contains: string; mode: "insensitive" }; model?: { contains: string; mode: "insensitive" }; brand?: { name: { contains: string; mode: "insensitive" } } }>;
  } = {
    status: "PUBLISHED",
  };

  if (filters.brand) {
    where.brand = { slug: filters.brand };
  }
  if (filters.type) where.type = filters.type;
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

  const orderBy: { priceCash?: "asc" | "desc"; yearModel?: "desc"; mileage?: "asc"; publishedAt?: "desc" }[] =
    filters.sort === "priceAsc"
      ? [{ priceCash: "asc" }]
      : filters.sort === "priceDesc"
        ? [{ priceCash: "desc" }]
        : filters.sort === "yearDesc"
          ? [{ yearModel: "desc" }]
          : filters.sort === "mileageAsc"
            ? [{ mileage: "asc" }]
            : [{ publishedAt: "desc" }];

  const [items, total] = await Promise.all([
    prisma.vehicle.findMany({
      where: where as object,
      orderBy: orderBy as object,
      skip,
      take: PAGE_SIZE,
      include: {
        brand: true,
        images: { orderBy: { sortOrder: "asc" }, take: 1 },
      },
    }),
    prisma.vehicle.count({ where: where as object }),
  ]);

  return {
    items,
    total,
    page,
    pageSize: PAGE_SIZE,
    totalPages: Math.ceil(total / PAGE_SIZE),
  };
}

export async function getBrandsForFilter() {
  return prisma.brand.findMany({
    where: { isActive: true },
    orderBy: { name: "asc" },
    select: { id: true, name: true, slug: true },
  });
}
