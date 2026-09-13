import { prisma } from "@/lib/db";
import {
  PUBLIC_CATALOG_PAGE_SIZE,
  buildPublicCatalogWhere,
  toPublicVehicleCard,
  type CatalogFilters,
} from "@/features/catalog/lib/public-catalog";

export type { CatalogFilters };

const PAGE_SIZE = PUBLIC_CATALOG_PAGE_SIZE;

function catalogOrderBy(sort: CatalogFilters["sort"]) {
  return sort === "priceAsc"
    ? [{ priceCash: "asc" as const }]
    : sort === "priceDesc"
      ? [{ priceCash: "desc" as const }]
      : sort === "yearDesc"
        ? [{ yearModel: "desc" as const }]
        : sort === "mileageAsc"
          ? [{ mileage: "asc" as const }]
          : [{ publishedAt: "desc" as const }];
}

export async function listPublicVehicles(filters: CatalogFilters = {}) {
  const page = Math.max(1, filters.page ?? 1);
  const skip = (page - 1) * PAGE_SIZE;
  const where = buildPublicCatalogWhere(filters);
  const orderBy = catalogOrderBy(filters.sort);

  const [rows, total] = await Promise.all([
    prisma.vehicle.findMany({
      where,
      orderBy,
      skip,
      take: PAGE_SIZE,
      include: {
        brand: true,
        images: { orderBy: { sortOrder: "asc" }, take: 1 },
      },
    }),
    prisma.vehicle.count({ where }),
  ]);

  return {
    items: rows.map(toPublicVehicleCard),
    total,
    page,
    pageSize: PAGE_SIZE,
    totalPages: Math.ceil(total / PAGE_SIZE),
  };
}

export async function getPublicPriceBounds() {
  const agg = await prisma.vehicle.aggregate({
    where: { status: "PUBLISHED", priceCash: { not: null } },
    _min: { priceCash: true },
    _max: { priceCash: true },
  });
  const min = agg._min.priceCash != null ? Math.floor(Number(agg._min.priceCash)) : 0;
  const max = agg._max.priceCash != null ? Math.ceil(Number(agg._max.priceCash)) : 300000;
  return { min, max: Math.max(min, max) };
}

export async function getPublicYearBounds() {
  const currentYear = new Date().getFullYear();
  const agg = await prisma.vehicle.aggregate({
    where: { status: "PUBLISHED", yearModel: { not: null } },
    _min: { yearModel: true },
    _max: { yearModel: true },
  });
  const min = agg._min.yearModel ?? 2000;
  const max = agg._max.yearModel ?? currentYear;
  return { min, max: Math.max(min, max) };
}

export async function getBrandsForFilter() {
  return prisma.brand.findMany({
    where: { isActive: true },
    orderBy: { name: "asc" },
    select: { id: true, name: true, slug: true },
  });
}

export async function getBrandsForVehicleForm() {
  const rows = await prisma.brand.findMany({
    where: { isActive: true },
    orderBy: { name: "asc" },
    select: {
      id: true,
      name: true,
      slug: true,
      _count: { select: { vehicles: true } },
    },
  });
  return rows.map((b) => ({
    id: b.id,
    name: b.name,
    slug: b.slug,
    vehicleCount: b._count.vehicles,
  }));
}

export async function getPartnersForVehicleForm() {
  return prisma.partner.findMany({
    where: { isActive: true },
    orderBy: { name: "asc" },
    select: { id: true, name: true, slug: true },
  });
}
