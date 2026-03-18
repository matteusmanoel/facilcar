import { prisma } from "@/lib/db";

export async function getSiteSettings() {
  const settings = await prisma.siteSettings.findFirst();
  return settings ?? null;
}
