import { prisma } from "@/lib/db";

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

export async function getRelatedVehicles(vehicleId: string, limit = 6) {
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

export async function getFeaturedVehicles(limit = 4) {
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
