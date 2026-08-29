import { BRAND } from "@/lib/brand";
import { formatPrintAddress, formatPrintTimestamp, type PrintSiteContext } from "@/features/vehicle/lib/print-document";

type Props = {
  site: PrintSiteContext;
  title: string;
  subtitle?: string | null;
  printedAt?: Date;
};

export function PrintDocumentHeader({ site, title, subtitle, printedAt }: Props) {
  const address = formatPrintAddress(site);
  const when = formatPrintTimestamp(printedAt);

  return (
    <header className="flex items-start justify-between gap-4 border-b border-zinc-300 pb-3">
      <div className="flex min-w-0 items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/facilcar-logo.jpg"
          alt=""
          className="h-10 w-10 rounded-md object-cover"
        />
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-[#ff6600]">
            {site.siteName || BRAND.name}
          </p>
          <h1 className="text-lg font-bold leading-tight text-zinc-900">{title}</h1>
          {subtitle ? <p className="mt-0.5 text-xs text-zinc-600">{subtitle}</p> : null}
        </div>
      </div>
      <div className="shrink-0 text-right text-[11px] leading-snug text-zinc-600">
        <p>Impresso em {when}</p>
        {address ? <p>{address}</p> : null}
        {site.whatsapp ? <p>WhatsApp {site.whatsapp}</p> : null}
        {site.phoneNumber ? <p>{site.phoneNumber}</p> : null}
      </div>
    </header>
  );
}
