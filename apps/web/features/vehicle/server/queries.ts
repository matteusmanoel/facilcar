import type { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import {
  PRINT_STOCK_LIMIT,
  applyPrintListDefaults,
  buildAdminVehicleWhere,
  type AdminVehicleFilterInput,
} from "@/features/vehicle/lib/admin-vehicle-filters";

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
  stockType: true,
  priceCash: true,
  updatedAt: true,
  brand: { select: { name: true } },
  images: { take: 1, orderBy: { sortOrder: "asc" as const }, select: { url: true } },
} as const;

export type AdminVehicleRow = Prisma.VehicleGetPayload<{ select: typeof ADMIN_VEHICLE_SELECT }>;

const PRINT_VEHICLE_SELECT = {
  id: true,
  title: true,
  status: true,
  type: true,
  model: true,
  version: true,
  yearManufacture: true,
  yearModel: true,
  mileage: true,
  fuelType: true,
  transmission: true,
  engineDisplacementLiters: true,
  color: true,
  doors: true,
  plateFinal: true,
  plate: true,
  priceCash: true,
  pricePromotional: true,
  priceTradeIn: true,
  stockType: true,
  commercialHistory: true,
  aceitaTroca: true,
  aceitaSemEntrada: true,
  featured: true,
  parcelaBase: true,
  entradaMinima: true,
  rendaMinimaSugerida: true,
  prioridade: true,
  city: true,
  state: true,
  brand: { select: { name: true } },
} as const;

export type PrintStockVehicle = Prisma.VehicleGetPayload<{ select: typeof PRINT_VEHICLE_SELECT }>;

export async function listAdminVehicles(
  opts: AdminVehicleFilterInput & { page: number; pageSize: number },
) {
  const where = buildAdminVehicleWhere(opts);
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

export async function listAdminVehiclesForPrint(opts: AdminVehicleFilterInput) {
  const where = buildAdminVehicleWhere(applyPrintListDefaults(opts));

  const [totalCount, vehicles] = await Promise.all([
    prisma.vehicle.count({ where }),
    prisma.vehicle.findMany({
      where,
      orderBy: [{ brand: { name: "asc" } }, { model: "asc" }, { yearModel: "asc" }],
      take: PRINT_STOCK_LIMIT,
      select: PRINT_VEHICLE_SELECT,
    }),
  ]);

  return { vehicles, totalCount, limit: PRINT_STOCK_LIMIT };
}

export async function getVehicleForCustomerSheet(id: string) {
  return prisma.vehicle.findUnique({
    where: { id },
    include: {
      brand: true,
      images: { orderBy: { sortOrder: "asc" as const } },
      features: { orderBy: { sortOrder: "asc" as const } },
    },
  });
}
