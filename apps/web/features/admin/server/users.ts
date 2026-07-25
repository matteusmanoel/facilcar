"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";
import { hashPassword } from "@/features/auth/server/passwords";
import {
  ForbiddenError,
  FULL_ACCESS_ROLES,
  UnauthorizedError,
  requireAdminRole,
} from "@/features/auth/server/rbac";
import {
  createUserSchema,
  resetPasswordSchema,
  updateUserSchema,
} from "@/schemas/user";

async function requireUserManager() {
  return requireAdminRole(FULL_ACCESS_ROLES);
}

export async function listUsers() {
  await requireUserManager();

  return prisma.user.findMany({
    orderBy: [{ isActive: "desc" }, { name: "asc" }],
    select: {
      id: true,
      name: true,
      email: true,
      role: true,
      isActive: true,
      lastLoginAt: true,
      createdAt: true,
    },
  });
}

export async function getUserById(id: string) {
  await requireUserManager();

  return prisma.user.findUnique({
    where: { id },
    select: {
      id: true,
      name: true,
      email: true,
      role: true,
      isActive: true,
      lastLoginAt: true,
      createdAt: true,
    },
  });
}

export async function createUserAction(input: unknown) {
  try {
    await requireUserManager();
  } catch (e) {
    if (e instanceof UnauthorizedError) return { ok: false as const, error: e.message };
    if (e instanceof ForbiddenError) return { ok: false as const, error: e.message };
    throw e;
  }

  const parsed = createUserSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false as const, error: parsed.error.flatten().fieldErrors };
  }

  const { name, email, password, role } = parsed.data;

  const existing = await prisma.user.findUnique({
    where: { email: email.toLowerCase().trim() },
    select: { id: true },
  });
  if (existing) {
    return { ok: false as const, error: { email: ["Este e-mail já está em uso"] } };
  }

  const passwordHash = await hashPassword(password);

  const user = await prisma.user.create({
    data: {
      name: name.trim(),
      email: email.toLowerCase().trim(),
      passwordHash,
      role,
    },
  });

  revalidatePath("/admin/usuarios");
  return { ok: true as const, id: user.id };
}

export async function updateUserAction(userId: string, input: unknown) {
  let currentUser: Awaited<ReturnType<typeof requireUserManager>>;
  try {
    currentUser = await requireUserManager();
  } catch (e) {
    if (e instanceof UnauthorizedError) return { ok: false as const, error: e.message };
    if (e instanceof ForbiddenError) return { ok: false as const, error: e.message };
    throw e;
  }

  const parsed = updateUserSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false as const, error: parsed.error.flatten().fieldErrors };
  }

  const target = await prisma.user.findUnique({
    where: { id: userId },
    select: { id: true, role: true },
  });
  if (!target) {
    return { ok: false as const, error: "Usuário não encontrado" };
  }

  if (userId === currentUser.user.id && !parsed.data.isActive) {
    return { ok: false as const, error: "Você não pode desativar sua própria conta" };
  }

  if (target.role === "SUPER_ADMIN" && parsed.data.role !== "SUPER_ADMIN") {
    const superAdminCount = await prisma.user.count({
      where: { role: "SUPER_ADMIN", isActive: true, id: { not: userId } },
    });
    if (superAdminCount === 0) {
      return { ok: false as const, error: "Deve existir ao menos um super admin ativo" };
    }
  }

  await prisma.user.update({
    where: { id: userId },
    data: {
      name: parsed.data.name.trim(),
      role: parsed.data.role,
      isActive: parsed.data.isActive,
    },
  });

  revalidatePath("/admin/usuarios");
  revalidatePath(`/admin/usuarios/${userId}`);
  return { ok: true as const };
}

export async function resetPasswordAction(userId: string, input: unknown) {
  try {
    await requireUserManager();
  } catch (e) {
    if (e instanceof UnauthorizedError) return { ok: false as const, error: e.message };
    if (e instanceof ForbiddenError) return { ok: false as const, error: e.message };
    throw e;
  }

  const parsed = resetPasswordSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false as const, error: parsed.error.flatten().fieldErrors };
  }

  const target = await prisma.user.findUnique({
    where: { id: userId },
    select: { id: true },
  });
  if (!target) {
    return { ok: false as const, error: "Usuário não encontrado" };
  }

  const passwordHash = await hashPassword(parsed.data.password);

  await prisma.user.update({
    where: { id: userId },
    data: { passwordHash },
  });

  revalidatePath(`/admin/usuarios/${userId}`);
  return { ok: true as const };
}

export async function canManageUsers(): Promise<boolean> {
  try {
    await requireUserManager();
    return true;
  } catch {
    return false;
  }
}
