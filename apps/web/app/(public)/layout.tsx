import { getSiteSettings } from "@/features/settings/server/queries";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";

export const dynamic = "force-dynamic";

export default async function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const settings = await getSiteSettings();

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        siteName={settings?.siteName}
        whatsappNumber={settings?.defaultWhatsappNumber ?? undefined}
      />
      <div className="flex-1">{children}</div>
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
    </div>
  );
}
