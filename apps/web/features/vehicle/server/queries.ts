import type { Prisma } from "@prisma/client";
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
