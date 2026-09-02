"use server";

import { revalidateTag } from "next/cache";
import {
  CONTENT_ROLES,
  ForbiddenError,
  UnauthorizedError,
  requireAdminRole,
} from "@/features/auth/server/rbac";
import { prisma } from "@/lib/db";
import { themeModeSchema } from "@/schemas/settings";

export async function updateSettingsAction(formData: FormData) {
  try {
    await requireAdminRole(CONTENT_ROLES);
  } catch (e) {
    if (e instanceof UnauthorizedError) return { success: false, error: e.message };
    if (e instanceof ForbiddenError) return { success: false, error: e.message };
    throw e;
  }

  const id = formData.get("id") as string;
  if (!id) return { success: false };

  const emptyToNull = (v: FormDataEntryValue | null) => {
    const s = typeof v === "string" ? v.trim() : "";
    return s === "" ? null : s;
  };

  const publicThemeRaw = formData.get("publicTheme");
  const publicTheme = themeModeSchema.safeParse(publicThemeRaw);
  if (!publicTheme.success) return { success: false };

  const parseFloat_ = (v: FormDataEntryValue | null): number | null => {
    const s = typeof v === "string" ? v.trim() : "";
    if (s === "") return null;
    const n = parseFloat(s);
    return isNaN(n) ? null : n;
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
      googleMapsUrl: emptyToNull(formData.get("googleMapsUrl")),
      latitude: parseFloat_(formData.get("latitude")),
      longitude: parseFloat_(formData.get("longitude")),
      facebookUrl: emptyToNull(formData.get("facebookUrl")),
      instagramUrl: emptyToNull(formData.get("instagramUrl")),
      youtubeUrl: emptyToNull(formData.get("youtubeUrl")),
      seoDefaultTitle: emptyToNull(formData.get("seoDefaultTitle")),
      seoDefaultDescription: emptyToNull(formData.get("seoDefaultDescription")),
      footerText: emptyToNull(formData.get("footerText")),
      heroTitle: emptyToNull(formData.get("heroTitle")),
      heroSubtitle: emptyToNull(formData.get("heroSubtitle")),
      publicTheme: publicTheme.data,
    },
  });
  revalidateTag("site-settings", "max");
  return { success: true };
}
