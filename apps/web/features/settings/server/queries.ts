import { unstable_cache } from "next/cache";
import { prisma } from "@/lib/db";

export const getSiteSettings = unstable_cache(
  async () => {
    const settings = await prisma.siteSettings.findFirst();
    return settings ?? null;
  },
  ["site-settings"],
  {
    tags: ["site-settings"],
    revalidate: 60,
  },
);
