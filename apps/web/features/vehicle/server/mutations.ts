"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";
import {
  ForbiddenError,
  UnauthorizedError,
  VEHICLE_WRITE_ROLES,
  requireAdminRole,
} from "@/features/auth/server/rbac";
import { createVehicleSchema } from "@/schemas/vehicle";
import type { VehicleStatus } from "@prisma/client";

const QUICK_STATUSES: VehicleStatus[] = ["DRAFT", "PUBLISHED", "RESERVED", "SOLD", "ARCHIVED"];

function parseBooleanField(value: FormDataEntryValue | null | undefined): boolean {
  return value === "on" || value === "true";
}

function parseVehicleFormBooleans(raw: Record<string, FormDataEntryValue>) {
  return {
    featured: parseBooleanField(raw.featured),
    aceitaTroca: parseBooleanField(raw.aceitaTroca),
    aceitaSemEntrada: parseBooleanField(raw.aceitaSemEntrada),
  };
}

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
  try {
    await requireAdminRole(VEHICLE_WRITE_ROLES);
  } catch (e) {
    if (e instanceof UnauthorizedError) return { ok: false, error: e.message };
    if (e instanceof ForbiddenError) return { ok: false, error: e.message };
    throw e;
  }

  const raw = Object.fromEntries(formData.entries());
  const parsed = createVehicleSchema.safeParse({
    ...raw,
    ...parseVehicleFormBooleans(raw),
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
      plateFinal: data.plateFinal?.trim() || null,
      priceCash: data.priceCash ?? null,
      priceTradeIn: data.priceTradeIn ?? null,
      pricePromotional: data.pricePromotional ?? null,
      city: data.city ?? null,
      state: data.state ?? null,
      featured: data.featured ?? false,
      aceitaTroca: data.aceitaTroca ?? false,
      aceitaSemEntrada: data.aceitaSemEntrada ?? false,
      parcelaBase: data.parcelaBase ?? null,
      entradaMinima: data.entradaMinima ?? null,
      rendaMinimaSugerida: data.rendaMinimaSugerida ?? null,
      prioridade: data.prioridade ?? 0,
      metaTitle: data.metaTitle ?? null,
      metaDescription: data.metaDescription ?? null,
      publishedAt: data.status === "PUBLISHED" ? new Date() : null,
      images: images.length ? { create: images } : undefined,
      features: features.length ? { create: features } : undefined,
    },
  });
  return { ok: true, id: vehicle.id, slug: vehicle.slug, title: vehicle.title, priceCash: vehicle.priceCash, status: vehicle.status, thumbnailUrl: images[0]?.url ?? null };
}

export async function updateVehicle(formData: FormData) {
  try {
    await requireAdminRole(VEHICLE_WRITE_ROLES);
  } catch (e) {
    if (e instanceof UnauthorizedError) return { ok: false, error: e.message };
    if (e instanceof ForbiddenError) return { ok: false, error: e.message };
    throw e;
  }

  const id = formData.get("id") as string;
  if (!id) return { ok: false, error: "id obrigatório" };

  const raw = Object.fromEntries(formData.entries());
  const parsed = createVehicleSchema.partial().safeParse({
    ...raw,
    ...parseVehicleFormBooleans(raw),
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
  if (data.plateFinal !== undefined) updatePayload.plateFinal = data.plateFinal?.trim() || null;
  if (data.priceCash !== undefined) updatePayload.priceCash = data.priceCash ?? null;
  if (data.priceTradeIn !== undefined) updatePayload.priceTradeIn = data.priceTradeIn ?? null;
  if (data.pricePromotional !== undefined) updatePayload.pricePromotional = data.pricePromotional ?? null;
  if (data.city !== undefined) updatePayload.city = data.city ?? null;
  if (data.state !== undefined) updatePayload.state = data.state ?? null;
  if (typeof data.featured === "boolean") updatePayload.featured = data.featured;
  if (typeof data.aceitaTroca === "boolean") updatePayload.aceitaTroca = data.aceitaTroca;
  if (typeof data.aceitaSemEntrada === "boolean") updatePayload.aceitaSemEntrada = data.aceitaSemEntrada;
  if (data.parcelaBase !== undefined) updatePayload.parcelaBase = data.parcelaBase ?? null;
  if (data.entradaMinima !== undefined) updatePayload.entradaMinima = data.entradaMinima ?? null;
  if (data.rendaMinimaSugerida !== undefined) updatePayload.rendaMinimaSugerida = data.rendaMinimaSugerida ?? null;
  if (data.prioridade !== undefined) updatePayload.prioridade = data.prioridade ?? 0;
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

export async function quickUpdateVehicleStatusAction(vehicleId: string, status: string) {
  await requireAdminRole(VEHICLE_WRITE_ROLES);

  if (!QUICK_STATUSES.includes(status as VehicleStatus)) {
    throw new Error("Status inválido");
  }

  const vehicleStatus = status as VehicleStatus;

  await prisma.vehicle.update({
    where: { id: vehicleId },
    data: {
      status: vehicleStatus,
      publishedAt: vehicleStatus === "PUBLISHED" ? new Date() : null,
    },
  });

  revalidatePath("/admin/veiculos");
  revalidatePath(`/admin/veiculos/${vehicleId}`);
}

export async function archiveVehicleAction(vehicleId: string) {
  await requireAdminRole(VEHICLE_WRITE_ROLES);

  const vehicle = await prisma.vehicle.findUnique({
    where: { id: vehicleId },
    select: { id: true, status: true },
  });

  if (!vehicle) {
    throw new Error("Veículo não encontrado");
  }

  if (vehicle.status === "ARCHIVED") {
    return;
  }

  await prisma.vehicle.update({
    where: { id: vehicleId },
    data: { status: "ARCHIVED" },
  });

  revalidatePath("/admin/veiculos");
  revalidatePath(`/admin/veiculos/${vehicleId}`);
}
