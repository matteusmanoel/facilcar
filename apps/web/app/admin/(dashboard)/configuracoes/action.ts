"use server";

import { prisma } from "@/lib/db";

export async function updateSettingsAction(formData: FormData) {
  const id = formData.get("id") as string;
  if (!id) return { success: false };

  await prisma.siteSettings.update({
    where: { id },
    data: {
      siteName: (formData.get("siteName") as string) ?? "",
      defaultWhatsappNumber: (formData.get("defaultWhatsappNumber") as string) ?? "",
      defaultEmail: (formData.get("defaultEmail") as string) ?? "",
      phoneNumber: (formData.get("phoneNumber") as string) || null,
      heroTitle: (formData.get("heroTitle") as string) || null,
      heroSubtitle: (formData.get("heroSubtitle") as string) || null,
    },
  });
  return { success: true };
}
