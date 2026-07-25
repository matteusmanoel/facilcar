import "server-only";

import { prisma } from "@/lib/db";
import { normalizePhone } from "./phone";

export type CustomerNameResolution = "keep_existing" | "use_new";

export type ResolveCustomerResult =
  | { ok: true; customerId: string; leadName: string }
  | {
      ok: false;
      conflict: {
        existingName: string;
        submittedName: string;
        customerId: string;
      };
    };

function namesMatch(a: string, b: string): boolean {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

/** Resolves customer by phone for lead creation, prompting on name conflicts. */
export async function resolveCustomerForLead(
  name: string,
  phone: string,
  email?: string | null,
  nameResolution?: CustomerNameResolution,
): Promise<ResolveCustomerResult> {
  const normalized = normalizePhone(phone);
  if (!normalized) {
    return { ok: true, customerId: "", leadName: name.trim() };
  }

  const trimmedName = name.trim();
  const trimmedEmail = email?.trim() || null;

  const existing = await prisma.customer.findUnique({
    where: { phone: normalized },
    select: { id: true, name: true },
  });

  if (!existing) {
    const created = await prisma.customer.create({
      data: { name: trimmedName, phone: normalized, email: trimmedEmail },
      select: { id: true },
    });
    return { ok: true, customerId: created.id, leadName: trimmedName };
  }

  if (!namesMatch(existing.name, trimmedName)) {
    if (!nameResolution) {
      return {
        ok: false,
        conflict: {
          existingName: existing.name,
          submittedName: trimmedName,
          customerId: existing.id,
        },
      };
    }

    if (nameResolution === "use_new") {
      await prisma.customer.update({
        where: { id: existing.id },
        data: {
          name: trimmedName,
          ...(trimmedEmail ? { email: trimmedEmail } : {}),
        },
      });
      return { ok: true, customerId: existing.id, leadName: trimmedName };
    }

    if (trimmedEmail) {
      await prisma.customer.update({
        where: { id: existing.id },
        data: { email: trimmedEmail },
      });
    }
    return { ok: true, customerId: existing.id, leadName: existing.name };
  }

  if (trimmedEmail) {
    await prisma.customer.update({
      where: { id: existing.id },
      data: { email: trimmedEmail },
    });
  }

  return { ok: true, customerId: existing.id, leadName: trimmedName };
}

/** Upserts a customer by normalized phone. Used when creating public leads (no conflict prompt). */
export async function upsertCustomerByPhone(
  name: string,
  phone: string,
  email?: string | null,
) {
  const normalized = normalizePhone(phone);
  if (!normalized) return null;

  return prisma.customer.upsert({
    where: { phone: normalized },
    create: {
      name: name.trim(),
      phone: normalized,
      email: email?.trim() || null,
    },
    update: {
      name: name.trim(),
      ...(email?.trim() ? { email: email.trim() } : {}),
    },
    select: { id: true },
  });
}
