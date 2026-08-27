"use server";

import { revalidatePath } from "next/cache";
import type { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import {
  ForbiddenError,
  UnauthorizedError,
  requireAdminRole,
  CUSTOMER_READ_ROLES,
  CUSTOMER_WRITE_ROLES,
} from "@/features/auth/server/rbac";
import { normalizePhone } from "@/features/customer/server/phone";
import { customerFormSchema } from "@/schemas/customer";

function handleAuthError(e: unknown) {
  if (e instanceof UnauthorizedError) return { ok: false as const, error: e.message };
  if (e instanceof ForbiddenError) return { ok: false as const, error: e.message };
  throw e;
}

const CUSTOMER_SELECT = {
  id: true,
  name: true,
  phone: true,
  email: true,
  createdAt: true,
  updatedAt: true,
  _count: { select: { leads: { where: { deletedAt: null } } } },
} as const;

export type AdminCustomerRow = Prisma.CustomerGetPayload<{ select: typeof CUSTOMER_SELECT }>;

export async function listCustomers(opts: {
  page: number;
  pageSize: number;
  search?: string;
}) {
  await requireAdminRole(CUSTOMER_READ_ROLES);

  const where: Prisma.CustomerWhereInput = {};
  const q = opts.search?.trim();
  if (q) {
    const normalized = normalizePhone(q);
    where.OR = [
      { name: { contains: q, mode: "insensitive" } },
      { phone: { contains: normalized || q } },
      ...(q.includes("@") ? [{ email: { contains: q, mode: "insensitive" as const } }] : []),
    ];
  }

  const skip = (Math.max(1, opts.page) - 1) * opts.pageSize;

  const [totalCount, customers] = await Promise.all([
    prisma.customer.count({ where }),
    prisma.customer.findMany({
      where,
      orderBy: { updatedAt: "desc" },
      skip,
      take: opts.pageSize,
      select: CUSTOMER_SELECT,
    }),
  ]);

  return { customers, totalCount };
}

export async function getCustomerById(id: string) {
  await requireAdminRole(CUSTOMER_READ_ROLES);

  return prisma.customer.findUnique({
    where: { id },
    select: {
      ...CUSTOMER_SELECT,
      leads: {
        where: { deletedAt: null },
        orderBy: { createdAt: "desc" },
        select: {
          id: true,
          type: true,
          status: true,
          createdAt: true,
        },
      },
    },
  });
}

export async function createCustomerAction(input: unknown) {
  try {
    await requireAdminRole(CUSTOMER_WRITE_ROLES);
  } catch (e) {
    return handleAuthError(e);
  }

  const parsed = customerFormSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false as const, error: parsed.error.flatten().fieldErrors };
  }

  const phone = normalizePhone(parsed.data.phone);
  if (phone.length < 10) {
    return { ok: false as const, error: { phone: ["Telefone inválido"] } };
  }

  const existing = await prisma.customer.findUnique({
    where: { phone },
    select: {
      id: true,
      name: true,
      phone: true,
      email: true,
      _count: { select: { leads: { where: { deletedAt: null } } } },
    },
  });
  if (existing) {
    return {
      ok: false as const,
      existingCustomer: {
        id: existing.id,
        name: existing.name,
        phone: existing.phone,
        email: existing.email,
        leadCount: existing._count.leads,
      },
      error: { phone: ["Já existe um cliente com este telefone"] },
    };
  }

  const email = parsed.data.email?.trim() || null;

  const customer = await prisma.customer.create({
    data: { name: parsed.data.name.trim(), phone, email },
    select: { id: true },
  });

  revalidatePath("/admin/leads");
  return { ok: true as const, id: customer.id };
}

export async function updateCustomerAction(id: string, input: unknown) {
  try {
    await requireAdminRole(CUSTOMER_WRITE_ROLES);
  } catch (e) {
    return handleAuthError(e);
  }

  const parsed = customerFormSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false as const, error: parsed.error.flatten().fieldErrors };
  }

  const phone = normalizePhone(parsed.data.phone);
  if (phone.length < 10) {
    return { ok: false as const, error: { phone: ["Telefone inválido"] } };
  }

  const conflict = await prisma.customer.findFirst({
    where: { phone, NOT: { id } },
  });
  if (conflict) {
    return { ok: false as const, error: { phone: ["Já existe um cliente com este telefone"] } };
  }

  const email = parsed.data.email?.trim() || null;

  await prisma.customer.update({
    where: { id },
    data: { name: parsed.data.name.trim(), phone, email },
  });

  revalidatePath("/admin/leads");
  return { ok: true as const };
}

export async function deleteCustomerAction(id: string) {
  try {
    await requireAdminRole(CUSTOMER_WRITE_ROLES);
  } catch (e) {
    return handleAuthError(e);
  }

  const leadCount = await prisma.lead.count({
    where: { customerId: id, deletedAt: null },
  });
  if (leadCount > 0) {
    return {
      ok: false as const,
      error: "Não é possível excluir cliente com leads vinculados.",
    };
  }

  await prisma.customer.delete({ where: { id } });
  revalidatePath("/admin/leads");
  return { ok: true as const };
}
