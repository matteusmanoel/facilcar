import type { Metadata } from "next";
import { getPageBySlug } from "./queries";
import { DEFAULT_OG_IMAGE, SITE_URL } from "@/lib/seo";

export async function cmsPageMetadata(
  slug: string,
  fallbackTitle: string,
): Promise<Metadata> {
  const page = await getPageBySlug(slug);
  const title = page?.metaTitle ?? page?.title ?? fallbackTitle;
  const description = page?.metaDescription ?? page?.excerpt ?? undefined;
  return {
    title,
    description,
    alternates: { canonical: `${SITE_URL}/${slug}` },
    openGraph: {
      title,
      description,
      locale: "pt_BR",
      type: "website",
      url: `${SITE_URL}/${slug}`,
      images: [{ url: DEFAULT_OG_IMAGE, alt: title }],
    },
  };
}
