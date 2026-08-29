import Link from "next/link";
import { notFound } from "next/navigation";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { printSiteFromSettings, toCustomerSheetModel } from "@/features/vehicle/lib/print-document";
import { listingQrSvg } from "@/features/vehicle/server/listing-qr";
import { getVehicleForCustomerSheet } from "@/features/vehicle/server/queries";
import { getSiteSettings } from "@/features/settings/server/queries";
import { PrintToolbar } from "@/features/vehicle/ui/print/PrintToolbar";
import { CustomerSheetDocument } from "@/features/vehicle/ui/print/CustomerSheetDocument";
import { BRAND } from "@/lib/brand";
import { SITE_URL } from "@/lib/seo";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ficha do veículo",
  robots: { index: false, follow: false },
};

export default async function AdminVehicleSheetPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await guardAdminSection("veiculos");
  const { id } = await params;
  const [vehicle, settings] = await Promise.all([
    getVehicleForCustomerSheet(id),
    getSiteSettings(),
  ]);

  if (!vehicle) notFound();

  const site = printSiteFromSettings(settings, SITE_URL, BRAND.name);
  const sheet = toCustomerSheetModel(vehicle, site);
  const closeHref = `/admin/veiculos/${id}`;

  if (!sheet) {
    return (
      <>
        <PrintToolbar closeHref={closeHref} closeLabel="Voltar ao veículo" showPrint={false} />
        <div className="mx-auto max-w-lg px-4 py-16 text-center">
          <h1 className="text-lg font-bold text-zinc-900">Ficha do cliente indisponível</h1>
          <p className="mt-2 text-sm text-zinc-600">
            A ficha A4 para o cliente está disponível apenas para veículos publicados.
          </p>
          <Link href={closeHref} className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-6")}>
            Voltar ao veículo
          </Link>
        </div>
      </>
    );
  }

  const qrSvg = await listingQrSvg(sheet.listingUrl);

  return (
    <>
      <PrintToolbar closeHref={closeHref} closeLabel="Voltar ao veículo" />
      <CustomerSheetDocument site={site} sheet={sheet} qrSvg={qrSvg} />
    </>
  );
}
