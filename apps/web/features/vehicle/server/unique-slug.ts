import { prisma } from "@/lib/db";
import { slugify } from "./slug";

export async function uniqueSlug(base: string, excludeId?: string): Promise<string> {
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

export { slugify };
