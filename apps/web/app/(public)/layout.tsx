import { getSiteSettings } from "@/features/settings/server/queries";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { WhatsAppFloat } from "@/components/shared/WhatsAppFloat";
import { buildAutoDealerJsonLd } from "@/lib/seo";

export default async function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const settings = await getSiteSettings();
  const jsonLd = settings ? buildAutoDealerJsonLd(settings) : null;

  return (
    <div
      className="flex min-h-screen flex-col"
      style={{
        colorScheme: "light",
        // Force light-mode CSS variables regardless of system theme
        ["--background" as string]: "#f4f4f5",
        ["--foreground" as string]: "#18181b",
        ["--facil-card" as string]: "#ffffff",
        ["--facil-surface" as string]: "#f9f9f9",
        ["--facil-border" as string]: "#e4e4e7",
        ["--facil-orange-light" as string]: "#fff3eb",
      }}
    >
      {jsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      )}
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
      <WhatsAppFloat whatsappNumber={settings?.defaultWhatsappNumber} />
    </div>
  );
}
