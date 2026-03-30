import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import { PostHogInit } from "@/components/analytics/PostHogInit";
import { BRAND } from "@/lib/brand";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";

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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
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
        {/* Dark mode temporariamente desativado — apenas light. Para reativar: remova forcedTheme,
            use defaultTheme="system" e enableSystem, e descomente ThemeToggle no AdminShell. */}
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem={false}
          forcedTheme="light"
          disableTransitionOnChange
        >
          <PostHogInit />
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
