import { guardAdminSection } from "@/features/auth/server/rbac";
import { parseAdminVehicleListParams } from "@/features/vehicle/lib/admin-vehicle-filters";
import { printSiteFromSettings, toStockListRow } from "@/features/vehicle/lib/print-document";
import { listAdminVehiclesForPrint } from "@/features/vehicle/server/queries";
import { getSiteSettings } from "@/features/settings/server/queries";
import { PrintToolbar } from "@/features/vehicle/ui/print/PrintToolbar";
import { StockListDocument } from "@/features/vehicle/ui/print/StockListDocument";
import { BRAND } from "@/lib/brand";
import { SITE_URL } from "@/lib/seo";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Imprimir estoque",
  robots: { index: false, follow: false },
};

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function AdminStockPrintPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  await guardAdminSection("veiculos");
  const parsed = parseAdminVehicleListParams(await searchParams);
  const [{ vehicles, totalCount, limit }, settings] = await Promise.all([
    listAdminVehiclesForPrint(parsed),
    getSiteSettings(),
  ]);

  const rows = vehicles.map(toStockListRow);
  const truncated = totalCount > vehicles.length;
  const showStatus = rows.some((row) => row.status !== "PUBLISHED");
  const site = printSiteFromSettings(settings, SITE_URL, BRAND.name);

  return (
    <>
      <PrintToolbar closeHref="/admin/veiculos" closeLabel="Voltar aos veículos" />
      {truncated ? (
        <p className="print:hidden border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
          Exibindo os primeiros {vehicles.length} de {totalCount} veículos (limite {limit}).
          Refine os filtros para imprimir um recorte menor.
        </p>
      ) : null}
      <StockListDocument
        site={site}
        rows={rows}
        totalCount={totalCount}
        truncated={truncated}
        showStatus={showStatus}
      />
    </>
  );
}
