"use server";

import { revalidateTag } from "next/cache";
import { prisma } from "@/lib/db";

export async function updateSettingsAction(formData: FormData) {
  const id = formData.get("id") as string;
  if (!id) return { success: false };

  const emptyToNull = (v: FormDataEntryValue | null) => {
    const s = typeof v === "string" ? v.trim() : "";
    return s === "" ? null : s;
  };

  await prisma.siteSettings.update({
    where: { id },
    data: {
      siteName: (formData.get("siteName") as string) ?? "",
      defaultWhatsappNumber: (formData.get("defaultWhatsappNumber") as string) ?? "",
      defaultEmail: (formData.get("defaultEmail") as string) ?? "",
      phoneNumber: emptyToNull(formData.get("phoneNumber")),
      addressLine: emptyToNull(formData.get("addressLine")),
      city: emptyToNull(formData.get("city")),
      state: emptyToNull(formData.get("state")),
      zipCode: emptyToNull(formData.get("zipCode")),
      facebookUrl: emptyToNull(formData.get("facebookUrl")),
      instagramUrl: emptyToNull(formData.get("instagramUrl")),
      youtubeUrl: emptyToNull(formData.get("youtubeUrl")),
      seoDefaultTitle: emptyToNull(formData.get("seoDefaultTitle")),
      seoDefaultDescription: emptyToNull(formData.get("seoDefaultDescription")),
      footerText: emptyToNull(formData.get("footerText")),
      heroTitle: emptyToNull(formData.get("heroTitle")),
      heroSubtitle: emptyToNull(formData.get("heroSubtitle")),
    },
  });
  revalidateTag("site-settings", "max");
  return { success: true };
}
