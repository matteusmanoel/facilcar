import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import { PostHogInit } from "@/components/analytics/PostHogInit";
import { AppThemeProvider } from "@/components/app-theme-provider";
import { getSiteSettings } from "@/features/settings/server/queries";
import { BRAND } from "@/lib/brand";
import { normalizePublicTheme } from "@/lib/theme";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL?.trim() || "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: BRAND.name,
    template: `%s | ${BRAND.name}`,
  },
  description: BRAND.defaultDescription,
  icons: {
    icon: "/facilcar-logo.jpg",
    apple: "/facilcar-logo.jpg",
  },
  openGraph: {
    title: BRAND.name,
    description: BRAND.defaultDescription,
    locale: "pt_BR",
    type: "website",
  },
};

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
