import type { Metadata } from "next";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { PublicNotFound } from "@/components/shared/PublicNotFound";
import { WhatsAppFloat } from "@/components/shared/WhatsAppFloat";
import { getSiteSettings } from "@/features/settings/server/queries";

export const metadata: Metadata = {
  title: "Página não encontrada",
  robots: { index: false, follow: false },
};

export default async function RootNotFound() {
  const settings = await getSiteSettings();

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Header
        siteName={settings?.siteName}
        whatsappNumber={settings?.defaultWhatsappNumber ?? undefined}
      />
      <div className="flex-1">
        <PublicNotFound />
      </div>
      <Footer
        siteName={settings?.siteName}
        footerText={settings?.footerText ?? undefined}
        whatsappNumber={settings?.defaultWhatsappNumber ?? undefined}
        phoneNumber={settings?.phoneNumber}
        defaultEmail={settings?.defaultEmail}
        addressLine={settings?.addressLine}
        city={settings?.city}
        state={settings?.state}
        zipCode={settings?.zipCode}
        instagramUrl={settings?.instagramUrl}
        facebookUrl={settings?.facebookUrl}
        youtubeUrl={settings?.youtubeUrl}
      />
      <WhatsAppFloat whatsappNumber={settings?.defaultWhatsappNumber} />
    </div>
  );
}
