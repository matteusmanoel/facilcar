import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Geist_Mono } from "next/font/google";
import { PostHogInit } from "@/components/analytics/PostHogInit";
import { BRAND } from "@/lib/brand";
import "./globals.css";

const plusJakarta = Plus_Jakarta_Sans({
  variable: "--font-plus-jakarta",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body
        className={`${plusJakarta.variable} ${geistMono.variable} antialiased`}
      >
        <PostHogInit />
        {children}
      </body>
    </html>
  );
}
