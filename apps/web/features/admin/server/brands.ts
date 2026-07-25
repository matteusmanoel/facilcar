"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";
import {
  ForbiddenError,
  UnauthorizedError,
  requireAdminRole,
  BRAND_READ_ROLES,
  BRAND_WRITE_ROLES,
} from "@/features/auth/server/rbac";
import { createBrandSchema, updateBrandSchema } from "@/schemas/brand";

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

async function uniqueSlug(base: string, excludeId?: string): Promise<string> {
  let suffix = 0;
  while (true) {
    const candidate = suffix === 0 ? base : `${base}-${suffix}`;
    const existing = await prisma.brand.findUnique({
      where: { slug: candidate },
      select: { id: true },
    });
    if (!existing || existing.id === excludeId) return candidate;
    suffix++;
  }
}

function handleAuthError(e: unknown) {
  if (e instanceof UnauthorizedError) return { ok: false as const, error: e.message };
  if (e instanceof ForbiddenError) return { ok: false as const, error: e.message };
  throw e;
}

export async function listBrands() {
  await requireAdminRole(BRAND_READ_ROLES);

  return prisma.brand.findMany({
    orderBy: [{ isActive: "desc" }, { name: "asc" }],
    select: {
      id: true,
      name: true,
      slug: true,
      logoUrl: true,
      isActive: true,
      _count: { select: { vehicles: true } },
    },
  });
}

export async function getBrandById(id: string) {
  await requireAdminRole(BRAND_READ_ROLES);

  return prisma.brand.findUnique({
    where: { id },
    select: {
      id: true,
      name: true,
      slug: true,
      logoUrl: true,
      isActive: true,
      _count: { select: { vehicles: true } },
    },
  });
}

export async function createBrandAction(input: unknown) {
  try {
    await requireAdminRole(BRAND_WRITE_ROLES);
  } catch (e) {
    return handleAuthError(e);
  }

  const parsed = createBrandSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false as const, error: parsed.error.flatten().fieldErrors };
  }

  const { name, slug: rawSlug, logoUrl, isActive } = parsed.data;
  const slug = await uniqueSlug(rawSlug?.trim() || slugify(name));

  const existing = await prisma.brand.findFirst({
    where: { OR: [{ name: name.trim() }, { slug }] },
    select: { id: true },
  });
  if (existing) {
    return { ok: false as const, error: "Já existe uma marca com este nome ou slug" };
  }

  const brand = await prisma.brand.create({
    data: {
      name: name.trim(),
      slug,
      logoUrl: logoUrl?.trim() || null,
      isActive,
    },
  });

  revalidatePath("/admin/marcas");
  revalidatePath("/admin/veiculos");
  return { ok: true as const, id: brand.id };
}

export async function updateBrandAction(brandId: string, input: unknown) {
  try {
    await requireAdminRole(BRAND_WRITE_ROLES);
  } catch (e) {
    return handleAuthError(e);
  }

  const parsed = updateBrandSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false as const, error: parsed.error.flatten().fieldErrors };
  }

  const target = await prisma.brand.findUnique({
    where: { id: brandId },
    select: { id: true },
  });
  if (!target) {
    return { ok: false as const, error: "Marca não encontrada" };
  }

  const { name, slug: rawSlug, logoUrl, isActive } = parsed.data;
  const slug = await uniqueSlug(rawSlug?.trim() || slugify(name), brandId);

  const conflict = await prisma.brand.findFirst({
    where: {
      id: { not: brandId },
      OR: [{ name: name.trim() }, { slug }],
    },
    select: { id: true },
  });
  if (conflict) {
    return { ok: false as const, error: "Já existe uma marca com este nome ou slug" };
  }

  await prisma.brand.update({
    where: { id: brandId },
    data: {
      name: name.trim(),
      slug,
      logoUrl: logoUrl?.trim() || null,
      isActive,
    },
  });

  revalidatePath("/admin/marcas");
  revalidatePath(`/admin/marcas/${brandId}`);
  revalidatePath("/admin/veiculos");
  return { ok: true as const };
}

export async function deactivateBrandAction(brandId: string) {
  try {
    await requireAdminRole(BRAND_WRITE_ROLES);
  } catch (e) {
    return handleAuthError(e);
  }

  const brand = await prisma.brand.findUnique({
    where: { id: brandId },
    select: { id: true, isActive: true },
  });
  if (!brand) {
    return { ok: false as const, error: "Marca não encontrada" };
  }

  if (!brand.isActive) {
    return { ok: true as const };
  }

  await prisma.brand.update({
    where: { id: brandId },
    data: { isActive: false },
  });

  revalidatePath("/admin/marcas");
  revalidatePath(`/admin/marcas/${brandId}`);
  revalidatePath("/admin/veiculos");
  return { ok: true as const };
}

export async function canManageBrands(): Promise<boolean> {
  try {
    await requireAdminRole(BRAND_WRITE_ROLES);
    return true;
  } catch {
    return false;
  }
}
