import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import { PostHogInit } from "@/components/analytics/PostHogInit";
import { AppThemeProvider } from "@/components/app-theme-provider";
import { getSiteSettings } from "@/features/settings/server/queries";
import { BRAND } from "@/lib/brand";
import { SITE_URL } from "@/lib/seo";
import { normalizePublicTheme } from "@/lib/theme";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export async function generateMetadata(): Promise<Metadata> {
  const settings = await getSiteSettings();
  const title = settings?.seoDefaultTitle?.trim() || BRAND.name;
  const description =
    settings?.seoDefaultDescription?.trim() || BRAND.defaultDescription;
  const siteName = settings?.siteName?.trim() || BRAND.name;

  return {
    metadataBase: new URL(SITE_URL),
    title: {
      default: title,
      template: `%s | ${siteName}`,
    },
    description,
    icons: {
      icon: "/facilcar-logo.jpg",
      apple: "/facilcar-logo.jpg",
    },
    openGraph: {
      title,
      description,
      locale: "pt_BR",
      type: "website",
      siteName,
      url: SITE_URL,
      images: [{ url: "/facilcar-logo.jpg", alt: siteName }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ["/facilcar-logo.jpg"],
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const settings = await getSiteSettings();
  const publicTheme = normalizePublicTheme(settings?.publicTheme);

  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Big+Shoulders:wght@700;800;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className={`${outfit.variable} antialiased`}>
        <AppThemeProvider publicTheme={publicTheme}>
          <PostHogInit />
          {children}
        </AppThemeProvider>
      </body>
    </html>
  );
}
