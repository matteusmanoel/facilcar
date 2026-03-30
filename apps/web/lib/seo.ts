const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL?.trim() || "http://localhost:3000";

type SiteSettingsForSeo = {
  siteName: string;
  defaultWhatsappNumber?: string;
  defaultEmail?: string;
  phoneNumber?: string | null;
  addressLine?: string | null;
  city?: string | null;
  state?: string | null;
  zipCode?: string | null;
  facebookUrl?: string | null;
  instagramUrl?: string | null;
  youtubeUrl?: string | null;
};

type VehicleForSeo = {
  title: string;
  slug: string;
  description?: string | null;
  shortDescription?: string | null;
  priceCash?: { toString(): string } | null;
  yearModel?: number | null;
  mileage?: number | null;
  color?: string | null;
  fuelType?: string | null;
  brand?: { name: string } | null;
  images?: Array<{ url: string; alt?: string | null }>;
};

type BlogPostForSeo = {
  title: string;
  slug: string;
  excerpt?: string | null;
  coverImageUrl?: string | null;
  publishedAt?: Date | null;
  updatedAt?: Date;
};

export function buildAutoDealerJsonLd(settings: SiteSettingsForSeo) {
  const addressParts: Record<string, string> = {};
  if (settings.addressLine) addressParts.streetAddress = settings.addressLine;
  if (settings.city) addressParts.addressLocality = settings.city;
  if (settings.state) addressParts.addressRegion = settings.state;
  if (settings.zipCode) addressParts.postalCode = settings.zipCode;

  const contactPoint = [];
  if (settings.phoneNumber) {
    contactPoint.push({
      "@type": "ContactPoint",
      telephone: settings.phoneNumber,
      contactType: "customer service",
      availableLanguage: "Portuguese",
    });
  }
  if (settings.defaultWhatsappNumber) {
    const wa = settings.defaultWhatsappNumber.replace(/\D/g, "");
    contactPoint.push({
      "@type": "ContactPoint",
      telephone: `+${wa}`,
      contactType: "sales",
      availableLanguage: "Portuguese",
    });
  }

  const sameAs: string[] = [];
  if (settings.facebookUrl) sameAs.push(settings.facebookUrl);
  if (settings.instagramUrl) sameAs.push(settings.instagramUrl);
  if (settings.youtubeUrl) sameAs.push(settings.youtubeUrl);

  return {
    "@context": "https://schema.org",
    "@type": "AutoDealer",
    name: settings.siteName,
    url: siteUrl,
    ...(settings.defaultEmail && { email: settings.defaultEmail }),
    ...(contactPoint.length > 0 && { contactPoint }),
    ...(Object.keys(addressParts).length > 0 && {
      address: {
        "@type": "PostalAddress",
        addressCountry: "BR",
        ...addressParts,
      },
    }),
    ...(sameAs.length > 0 && { sameAs }),
  };
}

export function buildCarJsonLd(vehicle: VehicleForSeo) {
  const url = `${siteUrl}/estoque/${vehicle.slug}`;
  const image = vehicle.images?.[0]?.url;

  const offers = vehicle.priceCash
    ? {
        "@type": "Offer",
        price: Number(vehicle.priceCash.toString()),
        priceCurrency: "BRL",
        availability: "https://schema.org/InStock",
        url,
      }
    : undefined;

  return {
    "@context": "https://schema.org",
    "@type": "Car",
    name: vehicle.title,
    url,
    description:
      vehicle.shortDescription ??
      vehicle.description?.slice(0, 300) ??
      undefined,
    ...(image && { image }),
    ...(vehicle.brand && { brand: { "@type": "Brand", name: vehicle.brand.name } }),
    ...(vehicle.yearModel && { modelDate: String(vehicle.yearModel) }),
    ...(vehicle.mileage != null && {
      mileageFromOdometer: {
        "@type": "QuantitativeValue",
        value: vehicle.mileage,
        unitCode: "KMT",
      },
    }),
    ...(vehicle.color && { color: vehicle.color }),
    ...(vehicle.fuelType && { fuelType: vehicle.fuelType }),
    ...(offers && { offers }),
  };
}

export function buildBlogPostingJsonLd(
  post: BlogPostForSeo,
  siteName: string,
) {
  const url = `${siteUrl}/blog/${post.slug}`;
  return {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    url,
    ...(post.excerpt && { description: post.excerpt }),
    ...(post.coverImageUrl && { image: post.coverImageUrl }),
    ...(post.publishedAt && {
      datePublished: post.publishedAt.toISOString(),
    }),
    ...(post.updatedAt && {
      dateModified: post.updatedAt.toISOString(),
    }),
    author: {
      "@type": "Organization",
      name: siteName,
      url: siteUrl,
    },
    publisher: {
      "@type": "Organization",
      name: siteName,
      url: siteUrl,
    },
  };
}
