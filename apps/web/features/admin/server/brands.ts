"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";
import {
  ForbiddenError,
  UnauthorizedError,
  requireAdminRole,
  BRAND_WRITE_ROLES,
} from "@/features/auth/server/rbac";
import { createBrandInlineSchema } from "@/schemas/brand";

function slugify(text: string): string {
  return (
    text
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-+|-+$/g, "") || "marca"
  );
}

async function uniqueSlug(base: string): Promise<string> {
  let suffix = 0;
  while (true) {
    const candidate = suffix === 0 ? base : `${base}-${suffix}`;
    const existing = await prisma.brand.findUnique({
      where: { slug: candidate },
      select: { id: true },
    });
    if (!existing) return candidate;
    suffix++;
  }
}

function handleAuthError(e: unknown) {
  if (e instanceof UnauthorizedError) return { ok: false as const, error: e.message };
  if (e instanceof ForbiddenError) return { ok: false as const, error: e.message };
  throw e;
}

export async function createBrandInlineAction(input: unknown) {
  try {
    await requireAdminRole(BRAND_WRITE_ROLES);
  } catch (e) {
    return handleAuthError(e);
  }

  const parsed = createBrandInlineSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false as const, error: parsed.error.issues[0]?.message ?? "Dados inválidos" };
  }

  const name = parsed.data.name.trim();
  const slug = await uniqueSlug(slugify(name));

  const existing = await prisma.brand.findFirst({
    where: { name: { equals: name, mode: "insensitive" } },
    select: { id: true, name: true, slug: true },
  });
  if (existing) {
    return {
      ok: true as const,
      brand: { ...existing, vehicleCount: 0 },
      alreadyExisted: true as const,
    };
  }

  const brand = await prisma.brand.create({
    data: { name, slug, isActive: true },
    select: { id: true, name: true, slug: true },
  });

  revalidatePath("/admin/veiculos");
  return {
    ok: true as const,
    brand: { ...brand, vehicleCount: 0 },
    alreadyExisted: false as const,
  };
}

export async function deleteBrandInlineAction(brandId: string) {
  try {
    await requireAdminRole(BRAND_WRITE_ROLES);
  } catch (e) {
    return handleAuthError(e);
  }

  const brand = await prisma.brand.findUnique({
    where: { id: brandId },
    select: { id: true, _count: { select: { vehicles: true } } },
  });
  if (!brand) {
    return { ok: false as const, error: "Marca não encontrada" };
  }
  if (brand._count.vehicles > 0) {
    return {
      ok: false as const,
      error: "Não é possível excluir marca vinculada a veículos.",
    };
  }

  await prisma.brand.delete({ where: { id: brandId } });
  revalidatePath("/admin/veiculos");
  return { ok: true as const };
}
