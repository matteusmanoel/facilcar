import type { CustomerSheetModel, PrintSiteContext } from "@/features/vehicle/lib/print-document";
import { PrintDocumentHeader } from "./PrintDocumentHeader";

type Props = {
  site: PrintSiteContext;
  sheet: CustomerSheetModel;
  qrSvg: string;
};

export function CustomerSheetDocument({ site, sheet, qrSvg }: Props) {
  return (
    <article className="print-sheet mx-auto flex min-h-[297mm] max-w-[210mm] flex-col px-6 py-5">
      <style>{`
        @page { size: A4 portrait; margin: 8mm; }
        @media print {
          .print-sheet { max-width: none; min-height: auto; padding: 0; }
        }
      `}</style>
      <PrintDocumentHeader site={site} title="Ficha do veículo" />

      <div className="mt-4 grid grid-cols-[1.15fr_0.85fr] gap-4">
        <div className="overflow-hidden rounded-lg bg-zinc-100">
          {sheet.coverUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={sheet.coverUrl}
              alt={sheet.title}
              className="h-[210px] w-full object-cover"
            />
          ) : (
            <div className="flex h-[210px] items-center justify-center text-sm text-zinc-400">
              Sem foto
            </div>
          )}
        </div>
        <div className="flex min-w-0 flex-col">
          <h2 className="text-xl font-extrabold uppercase leading-tight text-zinc-900">
            {sheet.title}
          </h2>
          {sheet.subtitle ? (
            <p className="mt-1 text-sm text-zinc-600">{sheet.subtitle}</p>
          ) : null}
          <p className="mt-3 text-3xl font-black tracking-tight text-[#ff6600]">
            {sheet.priceCashLabel}
          </p>
          {sheet.pricePromotionalLabel ? (
            <p className="mt-1 text-sm text-zinc-700">
              Promoção: <strong>{sheet.pricePromotionalLabel}</strong>
            </p>
          ) : null}
          {sheet.priceTradeInLabel ? (
            <p className="text-sm text-zinc-700">
              Troca a partir de <strong>{sheet.priceTradeInLabel}</strong>
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            {sheet.aceitaTroca ? (
              <span className="rounded-full bg-[#fff3eb] px-2.5 py-0.5 text-[11px] font-semibold text-[#ff6600]">
                Aceita troca
              </span>
            ) : null}
            {sheet.aceitaSemEntrada ? (
              <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-[11px] font-semibold text-zinc-700">
                Financiamento sujeito à análise
              </span>
            ) : null}
            {sheet.plateFinal ? (
              <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-[11px] font-semibold text-zinc-700">
                Final da placa {sheet.plateFinal}
              </span>
            ) : null}
          </div>
        </div>
      </div>

      {sheet.thumbUrls.length > 0 ? (
        <div className="mt-3 grid grid-cols-4 gap-2">
          {sheet.thumbUrls.map((url) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={url}
              src={url}
              alt=""
              className="h-16 w-full rounded-md object-cover"
            />
          ))}
        </div>
      ) : null}

      <section className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-lg bg-zinc-50 p-3 text-sm">
        {sheet.specs.map((spec) => (
          <div key={spec.label} className="flex justify-between gap-3">
            <span className="text-zinc-500">{spec.label}</span>
            <span className="font-semibold text-zinc-900">{spec.value}</span>
          </div>
        ))}
      </section>

      {sheet.features.visible.length > 0 ? (
        <section className="mt-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Opcionais e equipamentos
          </h3>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {sheet.features.visible.map((label) => (
              <li
                key={label}
                className="rounded-md border border-zinc-200 bg-white px-2 py-0.5 text-[11px] text-zinc-800"
              >
                {label}
              </li>
            ))}
            {sheet.features.remaining > 0 ? (
              <li className="px-2 py-0.5 text-[11px] text-zinc-500">
                e mais {sheet.features.remaining}
              </li>
            ) : null}
          </ul>
        </section>
      ) : null}

      {sheet.shortDescription ? (
        <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-zinc-600">
          {sheet.shortDescription}
        </p>
      ) : null}

      <div className="mt-auto flex items-end justify-between gap-4 border-t border-zinc-200 pt-3">
        <div className="text-[11px] leading-snug text-zinc-600">
          <p>Escaneie para ver este veículo no site.</p>
          <p className="mt-2">
            Preços e disponibilidade sujeitos a alteração. Financiamento sujeito à análise de
            crédito e às condições da financeira.
          </p>
        </div>
        <div className="print-qr h-24 w-24 shrink-0" dangerouslySetInnerHTML={{ __html: qrSvg }} />
      </div>
    </article>
  );
}
