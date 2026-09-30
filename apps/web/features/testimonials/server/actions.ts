"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";
import { requireAdminRole } from "@/features/auth/server/rbac";
import { CONTENT_ROLES } from "@/features/auth/rbac-config";
import { z } from "zod";

const schema = z.object({
  name: z.string().min(2, "Nome obrigatório"),
  comment: z.string().min(10, "Depoimento obrigatório"),
  imageUrl: z.string().url("URL de imagem inválida"),
  sortOrder: z.coerce.number().int().default(0),
  published: z.boolean().default(false),
});

export async function createTestimonialAction(
  data: z.infer<typeof schema>,
): Promise<{ id: string }> {
  await requireAdminRole(CONTENT_ROLES);
  const parsed = schema.parse(data);
  const result = await prisma.testimonial.create({ data: parsed });
  revalidatePath("/admin/depoimentos");
  revalidatePath("/");
  return { id: result.id };
}

export async function updateTestimonialAction(
  id: string,
  data: Partial<z.infer<typeof schema>>,
): Promise<void> {
  await requireAdminRole(CONTENT_ROLES);
  const partial = schema.partial().parse(data);
  await prisma.testimonial.update({ where: { id }, data: partial });
  revalidatePath("/admin/depoimentos");
  revalidatePath("/");
}

export async function deleteTestimonialAction(id: string): Promise<void> {
  await requireAdminRole(CONTENT_ROLES);
  await prisma.testimonial.delete({ where: { id } });
  revalidatePath("/admin/depoimentos");
  revalidatePath("/");
}
