"use server";

import { prisma } from "@/lib/db";
import { createVehicleSchema } from "@/schemas/vehicle";
import type { VehicleStatus } from "@prisma/client";

function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "")
    || "veiculo";
}

async function uniqueSlug(base: string, excludeId?: string): Promise<string> {
  let suffix = 0;
  while (true) {
    const candidate = suffix === 0 ? base : `${base}-${suffix}`;
    const existing = await prisma.vehicle.findUnique({
      where: { slug: candidate },
      select: { id: true },
    });
    if (!existing || existing.id === excludeId) return candidate;
    suffix++;
  }
}

function parseImageUrls(value: string | undefined): { url: string; sortOrder: number; isCover: boolean }[] {
  if (!value?.trim()) return [];
  return value
    .trim()
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean)
    .map((url, i) => ({ url, sortOrder: i, isCover: i === 0 }));
}

function parseFeatures(value: string | undefined): { label: string; category: "OTHER"; sortOrder: number }[] {
  if (!value?.trim()) return [];
  return value
    .trim()
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((label, i) => ({ label, category: "OTHER" as const, sortOrder: i }));
}

export async function createVehicle(formData: FormData) {
  const raw = Object.fromEntries(formData.entries());
  const parsed = createVehicleSchema.safeParse({
    ...raw,
    featured: raw.featured === "on" || raw.featured === "true",
  });
  if (!parsed.success) return { ok: false, error: parsed.error.flatten().fieldErrors };

  const { imageUrls, features: featuresStr, ...data } = parsed.data;
  const images = parseImageUrls(imageUrls);
  const features = parseFeatures(featuresStr);

  const baseSlug = data.slug?.trim() || slugify(data.title);
  const slug = await uniqueSlug(baseSlug);

  const vehicle = await prisma.vehicle.create({
    data: {
      slug,
      status: data.status as VehicleStatus,
      type: data.type,
      title: data.title,
      shortDescription: data.shortDescription ?? null,
      description: data.description ?? null,
      brandId: data.brandId,
      model: data.model,
      version: data.version ?? null,
      yearManufacture: data.yearManufacture ?? null,
      yearModel: data.yearModel ?? null,
      mileage: data.mileage ?? null,
      fuelType: data.fuelType ?? null,
      transmission: data.transmission ?? null,
      color: data.color ?? null,
      doors: data.doors ?? null,
      priceCash: data.priceCash ?? null,
      priceTradeIn: data.priceTradeIn ?? null,
      pricePromotional: data.pricePromotional ?? null,
      city: data.city ?? null,
      state: data.state ?? null,
      featured: data.featured ?? false,
      metaTitle: data.metaTitle ?? null,
      metaDescription: data.metaDescription ?? null,
      publishedAt: data.status === "PUBLISHED" ? new Date() : null,
      images: images.length ? { create: images } : undefined,
      features: features.length ? { create: features } : undefined,
    },
  });
  return { ok: true, id: vehicle.id };
}

export async function updateVehicle(formData: FormData) {
  const id = formData.get("id") as string;
  if (!id) return { ok: false, error: "id obrigatório" };

  const raw = Object.fromEntries(formData.entries());
  const parsed = createVehicleSchema.partial().safeParse({
    ...raw,
    featured: raw.featured === "on" || raw.featured === "true",
  });
  if (!parsed.success) return { ok: false, error: parsed.error.flatten().fieldErrors };

  const { imageUrls, features: featuresStr, ...data } = parsed.data;

  const updatePayload: Record<string, unknown> = {};
  if (data.slug != null) updatePayload.slug = data.slug;
  if (data.status != null) {
    updatePayload.status = data.status;
    updatePayload.publishedAt = data.status === "PUBLISHED" ? new Date() : null;
  }
  if (data.type != null) updatePayload.type = data.type;
  if (data.title != null) updatePayload.title = data.title;
  if (data.shortDescription !== undefined) updatePayload.shortDescription = data.shortDescription ?? null;
  if (data.description !== undefined) updatePayload.description = data.description ?? null;
  if (data.brandId != null) updatePayload.brandId = data.brandId;
  if (data.model != null) updatePayload.model = data.model;
  if (data.version !== undefined) updatePayload.version = data.version ?? null;
  if (data.yearManufacture !== undefined) updatePayload.yearManufacture = data.yearManufacture ?? null;
  if (data.yearModel !== undefined) updatePayload.yearModel = data.yearModel ?? null;
  if (data.mileage !== undefined) updatePayload.mileage = data.mileage ?? null;
  if (data.fuelType !== undefined) updatePayload.fuelType = data.fuelType ?? null;
  if (data.transmission !== undefined) updatePayload.transmission = data.transmission ?? null;
  if (data.color !== undefined) updatePayload.color = data.color ?? null;
  if (data.doors !== undefined) updatePayload.doors = data.doors ?? null;
  if (data.priceCash !== undefined) updatePayload.priceCash = data.priceCash ?? null;
  if (data.priceTradeIn !== undefined) updatePayload.priceTradeIn = data.priceTradeIn ?? null;
  if (data.pricePromotional !== undefined) updatePayload.pricePromotional = data.pricePromotional ?? null;
  if (data.city !== undefined) updatePayload.city = data.city ?? null;
  if (data.state !== undefined) updatePayload.state = data.state ?? null;
  if (typeof data.featured === "boolean") updatePayload.featured = data.featured;
  if (data.metaTitle !== undefined) updatePayload.metaTitle = data.metaTitle ?? null;
  if (data.metaDescription !== undefined) updatePayload.metaDescription = data.metaDescription ?? null;

  if (imageUrls !== undefined) {
    await prisma.vehicleImage.deleteMany({ where: { vehicleId: id } });
    const images = parseImageUrls(imageUrls);
    if (images.length)
      await prisma.vehicleImage.createMany({
        data: images.map((img) => ({ ...img, vehicleId: id })),
      });
  }
  if (featuresStr !== undefined) {
    await prisma.vehicleFeature.deleteMany({ where: { vehicleId: id } });
    const features = parseFeatures(featuresStr);
    if (features.length)
      await prisma.vehicleFeature.createMany({
        data: features.map((f) => ({ ...f, vehicleId: id })),
      });
  }

  await prisma.vehicle.update({
    where: { id },
    data: updatePayload as Parameters<typeof prisma.vehicle.update>[0]["data"],
  });
  return { ok: true, id };
}
