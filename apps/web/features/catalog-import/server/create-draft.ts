import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { slugify } from "@/features/vehicle/server/slug";
import { uniqueSlug } from "@/features/vehicle/server/unique-slug";
import type { VehicleImportInput } from "./classify";
import { computeVehicleFingerprint } from "./classify";
import { validateVehicleImportInput } from "./validate";
import { normalizeEngineDisplacementLiters } from "@/features/vehicle/lib/engine-displacement";

async function resolveBrandId(brandName: string | null): Promise<string> {
  const name = (brandName?.trim() || "Outros").slice(0, 80);
  const slug = slugify(name);
  const existing = await prisma.brand.findFirst({
    where: { OR: [{ name: { equals: name, mode: "insensitive" } }, { slug }] },
  });
  if (existing) return existing.id;
  const created = await prisma.brand.create({
    data: { name, slug: await uniqueBrandSlug(slug), isActive: true },
  });
  return created.id;
}

async function uniqueBrandSlug(base: string): Promise<string> {
  let suffix = 0;
  while (true) {
    const candidate = suffix === 0 ? base : `${base}-${suffix}`;
    const existing = await prisma.brand.findUnique({ where: { slug: candidate } });
    if (!existing) return candidate;
    suffix++;
  }
}

export async function createDraftFromImport(itemId: string): Promise<{
  vehicleId: string | null;
  status: "IMPORTED" | "FAILED";
  warnings: string[];
  error?: string;
}> {
  const item = await prisma.catalogImportItem.findUnique({
    where: { id: itemId },
    include: {
      events: { orderBy: { sequence: "asc" } },
      mediaAssets: {
        where: { status: { in: ["UPLOADED", "SKIPPED_DEDUPED"] } },
        include: { blob: true },
        orderBy: { sortOrder: "asc" },
      },
    },
  });
  if (!item) return { vehicleId: null, status: "FAILED", warnings: [], error: "item_not_found" };
  if (item.vehicleId) {
    await prisma.catalogImportItem.update({
      where: { id: itemId },
      data: { status: "IMPORTED", completedAt: new Date(), lockedAt: null, lockedBy: null },
    });
    await prisma.catalogImportEvent.updateMany({
      where: { importItemId: itemId },
      data: { processingStatus: "PROCESSED" },
    });
    return { vehicleId: item.vehicleId, status: "IMPORTED", warnings: item.warnings };
  }

  const parsed = item.parsedJson as VehicleImportInput | null;
  if (!parsed) {
    return { vehicleId: null, status: "FAILED", warnings: item.warnings, error: "missing_parsed_json" };
  }

  const validation = validateVehicleImportInput(parsed, item.rawText);
  const warnings = [...item.warnings, ...validation.warnings];
  if (!validation.valid) {
    await prisma.catalogImportItem.update({
      where: { id: itemId },
      data: {
        status: "FAILED",
        error: validation.errors.join(","),
        warnings,
        lockedAt: null,
        lockedBy: null,
      },
    });
    return { vehicleId: null, status: "FAILED", warnings, error: validation.errors.join(",") };
  }

  if (item.mediaAssets.length === 0) warnings.push("NO_MEDIA");

  const engineLiters = warnings.includes("ENGINE_AMBIGUOUS")
    ? null
    : normalizeEngineDisplacementLiters(parsed.engineDisplacementLiters);

  const fingerprint = computeVehicleFingerprint(parsed);
  const dup = await prisma.catalogImportItem.findFirst({
    where: {
      vehicleFingerprint: fingerprint,
      status: "IMPORTED",
      id: { not: itemId },
      vehicleId: { not: null },
    },
  });
  if (dup) warnings.push("POSSIBLE_DUPLICATE");

  const brandId = await resolveBrandId(parsed.brand);
  const title =
    parsed.title?.trim() ||
    [parsed.brand, parsed.model, parsed.version, parsed.yearModel].filter(Boolean).join(" ");
  const slug = await uniqueSlug(slugify(title || "veiculo-importado"));

  let priceCash: Prisma.Decimal | null = null;
  if (parsed.priceCash) {
    try {
      priceCash = new Prisma.Decimal(parsed.priceCash);
    } catch {
      warnings.push("invalid_priceCash");
    }
  }

  const vehicle = await prisma.$transaction(async (tx) => {
    const v = await tx.vehicle.create({
      data: {
        slug,
        status: "DRAFT",
        type: "CAR",
        title,
        shortDescription: parsed.shortDescription,
        description: parsed.description ?? item.rawText,
        brandId,
        model: parsed.model!.trim(),
        version: parsed.version,
        yearManufacture: parsed.yearManufacture,
        yearModel: parsed.yearModel,
        mileage: parsed.mileage,
        fuelType: parsed.fuel,
        transmission: parsed.transmission,
        engineDisplacementLiters: engineLiters,
        color: parsed.color,
        priceCash,
        publishedAt: null,
        images: {
          create: item.mediaAssets
            .filter((a) => a.blob?.publicUrl)
            .map((a, i) => ({
              url: a.blob!.publicUrl,
              sortOrder: a.sortOrder,
              isCover: i === 0,
            })),
        },
        features: {
          create: parsed.features.map((label, i) => ({
            label,
            category: "OTHER" as const,
            sortOrder: i,
          })),
        },
      },
    });

    await tx.catalogImportItem.update({
      where: { id: itemId },
      data: {
        vehicleId: v.id,
        vehicleFingerprint: fingerprint,
        status: "IMPORTED",
        parsedJson: parsed as object,
        warnings,
        completedAt: new Date(),
        lockedAt: null,
        lockedBy: null,
        error: null,
      },
    });
    await tx.catalogImportEvent.updateMany({
      where: { importItemId: itemId },
      data: { processingStatus: "PROCESSED" },
    });
    return v;
  });

  return { vehicleId: vehicle.id, status: "IMPORTED", warnings };
}
