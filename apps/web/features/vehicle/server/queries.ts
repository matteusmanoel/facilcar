import type { FuelType, Prisma, Transmission, VehicleStatus, VehicleType } from "@prisma/client";
import { prisma } from "@/lib/db";

/** Lista de veículo com marca + imagens (cards / relacionados). Exportado para páginas evitarem `any` com `Promise.all`. */
export type VehicleWithBrandAndPreviewImages = Prisma.VehicleGetPayload<{
  include: {
    brand: true;
    images: true;
  };
}>;

export async function getVehicleBySlug(slug: string) {
  return prisma.vehicle.findUnique({
    where: { slug, status: "PUBLISHED" },
    include: {
      brand: true,
      images: { orderBy: { sortOrder: "asc" } },
      features: { orderBy: { sortOrder: "asc" } },
    },
  });
}

export async function getRelatedVehicles(
  vehicleId: string,
  limit = 6
): Promise<VehicleWithBrandAndPreviewImages[]> {
  const vehicle = await prisma.vehicle.findUnique({
    where: { id: vehicleId },
    select: { brandId: true, type: true },
  });
  if (!vehicle) return [];

  return prisma.vehicle.findMany({
    where: {
      id: { not: vehicleId },
      status: "PUBLISHED",
      OR: [{ brandId: vehicle.brandId }, { type: vehicle.type }],
    },
    take: limit,
    include: {
      brand: true,
      images: { orderBy: { sortOrder: "asc" }, take: 1 },
    },
  });
}

export async function getFeaturedVehicles(
  limit = 4
): Promise<VehicleWithBrandAndPreviewImages[]> {
  return prisma.vehicle.findMany({
    where: { status: "PUBLISHED", featured: true },
    orderBy: { publishedAt: "desc" },
    take: limit,
    include: {
      brand: true,
      images: { orderBy: { sortOrder: "asc" }, take: 1 },
    },
  });
}

const ADMIN_VEHICLE_SELECT = {
  id: true,
  slug: true,
  title: true,
  status: true,
  priceCash: true,
  updatedAt: true,
  brand: { select: { name: true } },
  images: { take: 1, orderBy: { sortOrder: "asc" as const }, select: { url: true } },
} as const;

export type AdminVehicleRow = Prisma.VehicleGetPayload<{ select: typeof ADMIN_VEHICLE_SELECT }>;

export async function listAdminVehicles(opts: {
  page: number;
  pageSize: number;
  statuses?: VehicleStatus[];
  search?: string;
  brandIds?: string[];
  types?: VehicleType[];
  featuredValues?: boolean[];
  fuelTypes?: FuelType[];
  transmissions?: Transmission[];
  priceMin?: number;
  priceMax?: number;
  yearMin?: number;
  yearMax?: number;
}) {
  const where: Prisma.VehicleWhereInput = {};
  if (opts.statuses?.length) where.status = { in: opts.statuses };
  if (opts.brandIds?.length) where.brandId = { in: opts.brandIds };
  if (opts.types?.length) where.type = { in: opts.types };
  if (opts.fuelTypes?.length) where.fuelType = { in: opts.fuelTypes };
  if (opts.transmissions?.length) where.transmission = { in: opts.transmissions };

  if (opts.featuredValues?.length === 1) {
    where.featured = opts.featuredValues[0];
  }

  if (opts.priceMin != null || opts.priceMax != null) {
    where.priceCash = {
      ...(opts.priceMin != null ? { gte: opts.priceMin } : {}),
      ...(opts.priceMax != null ? { lte: opts.priceMax } : {}),
    };
  }

  if (opts.yearMin != null || opts.yearMax != null) {
    where.yearModel = {
      ...(opts.yearMin != null ? { gte: opts.yearMin } : {}),
      ...(opts.yearMax != null ? { lte: opts.yearMax } : {}),
    };
  }

  const q = opts.search?.trim();
  if (q) {
    where.OR = [
      { title: { contains: q, mode: "insensitive" } },
      { model: { contains: q, mode: "insensitive" } },
      { slug: { contains: q, mode: "insensitive" } },
      { brand: { name: { contains: q, mode: "insensitive" } } },
    ];
  }

  const skip = (Math.max(1, opts.page) - 1) * opts.pageSize;

  const [totalCount, vehicles] = await Promise.all([
    prisma.vehicle.count({ where }),
    prisma.vehicle.findMany({
      where,
      orderBy: { updatedAt: "desc" },
      skip,
      take: opts.pageSize,
      select: ADMIN_VEHICLE_SELECT,
    }),
  ]);

  return { vehicles, totalCount };
}
