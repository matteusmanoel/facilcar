import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { PostHogInit } from "@/components/analytics/PostHogInit";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Auto Dealer Demo",
  description: "Estoque de veículos seminovos",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <PostHogInit />
        {children}
      </body>
    </html>
  );
}
