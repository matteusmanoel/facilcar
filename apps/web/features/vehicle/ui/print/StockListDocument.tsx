import type { StockListRow } from "@/features/vehicle/lib/print-document";
import type { PrintSiteContext } from "@/features/vehicle/lib/print-document";
import { PrintDocumentHeader } from "./PrintDocumentHeader";

type Props = {
  site: PrintSiteContext;
  rows: StockListRow[];
  totalCount: number;
  truncated: boolean;
  showStatus: boolean;
};

function flagCell(row: StockListRow): string {
  const flags: string[] = [];
  if (row.aceitaTroca) flags.push("Troca");
  if (row.aceitaSemEntrada) flags.push("S/ entrada");
  if (row.featured) flags.push("Destaque");
  return flags.join(" · ") || "—";
}

export function StockListDocument({
  site,
  rows,
  totalCount,
  truncated,
  showStatus,
}: Props) {
  const subtitle = truncated
    ? `${rows.length} de ${totalCount} veículos (limite da impressão)`
    : `${rows.length} veículo(s)`;

  return (
    <article className="print-stock mx-auto max-w-[280mm] px-4 py-4">
      <style>{`
        @page { size: A4 landscape; margin: 8mm; }
        @media print {
          .print-stock { max-width: none; padding: 0; }
        }
      `}</style>
      <PrintDocumentHeader site={site} title="Estoque interno" subtitle={subtitle} />

      {rows.length === 0 ? (
        <p className="mt-8 text-center text-sm text-zinc-600">Nenhum veículo para imprimir.</p>
      ) : (
        <table className="mt-3 w-full border-collapse text-[10px] leading-tight text-zinc-900">
          <thead>
            <tr className="border-b border-zinc-400 bg-zinc-100 text-center text-[9px] uppercase tracking-wide text-zinc-600">
              <th colSpan={2} className="px-1.5 py-1.5 font-semibold">
                Identificação
              </th>
              <th colSpan={8} className="px-1.5 py-1.5 font-semibold">
                Ficha
              </th>
              <th colSpan={3} className="px-1.5 py-1.5 font-semibold">
                Preços
              </th>
              <th className="px-1.5 py-1.5 font-semibold">Flags</th>
              <th colSpan={4} className="px-1.5 py-1.5 font-semibold">
                Interno *
              </th>
              {showStatus ? <th className="px-1.5 py-1.5 font-semibold">Status</th> : null}
            </tr>
            <tr className="border-b border-zinc-300 bg-zinc-50 text-center text-[9px] font-semibold text-zinc-500">
              <th className="px-1.5 py-1">Veículo</th>
              <th className="px-1.5 py-1">Tipo</th>
              <th className="px-1.5 py-1">Ano</th>
              <th className="px-1.5 py-1">KM</th>
              <th className="px-1.5 py-1">Comb.</th>
              <th className="px-1.5 py-1">Câmbio</th>
              <th className="px-1.5 py-1">Motor</th>
              <th className="px-1.5 py-1">Cor</th>
              <th className="px-1.5 py-1">Pt</th>
              <th className="px-1.5 py-1">Placa</th>
              <th className="px-1.5 py-1">À vista</th>
              <th className="px-1.5 py-1">Promo</th>
              <th className="px-1.5 py-1">Troca</th>
              <th className="px-1.5 py-1">Comercial</th>
              <th className="px-1.5 py-1">Parcela</th>
              <th className="px-1.5 py-1">Entrada</th>
              <th className="px-1.5 py-1">Renda</th>
              <th className="px-1.5 py-1">Pri.</th>
              {showStatus ? <th className="px-1.5 py-1">Status</th> : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="break-inside-avoid border-b border-zinc-200">
                <td className="px-1.5 py-1.5 font-medium">
                  <div>{row.identity}</div>
                  <div className="text-[9px] text-zinc-500">{row.location}</div>
                </td>
                <td className="px-1.5 py-1.5">{row.typeLabel}</td>
                <td className="whitespace-nowrap px-1.5 py-1.5">{row.yearLabel}</td>
                <td className="whitespace-nowrap px-1.5 py-1.5">{row.mileageLabel}</td>
                <td className="px-1.5 py-1.5">{row.fuelLabel}</td>
                <td className="px-1.5 py-1.5">{row.transmissionLabel}</td>
                <td className="whitespace-nowrap px-1.5 py-1.5">{row.engineLabel}</td>
                <td className="px-1.5 py-1.5">{row.color}</td>
                <td className="px-1.5 py-1.5">{row.doorsLabel}</td>
                <td className="px-1.5 py-1.5">{row.plateFinal}</td>
                <td className="whitespace-nowrap px-1.5 py-1.5 font-semibold">{row.priceCashLabel}</td>
                <td className="whitespace-nowrap px-1.5 py-1.5">{row.pricePromotionalLabel}</td>
                <td className="whitespace-nowrap px-1.5 py-1.5">{row.priceTradeInLabel}</td>
                <td className="px-1.5 py-1.5">{flagCell(row)}</td>
                <td className="whitespace-nowrap px-1.5 py-1.5">{row.parcelaBaseLabel}</td>
                <td className="whitespace-nowrap px-1.5 py-1.5">{row.entradaMinimaLabel}</td>
                <td className="whitespace-nowrap px-1.5 py-1.5">{row.rendaMinimaLabel}</td>
                <td className="px-1.5 py-1.5">{row.prioridade}</td>
                {showStatus ? <td className="px-1.5 py-1.5">{row.statusLabel}</td> : null}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <footer className="mt-4 space-y-1 text-[10px] text-zinc-600">
        <p>
          * Parcela, entrada e renda são referência interna — não são oferta ao cliente. O vendedor
          decide qual preço usar (à vista, promocional ou troca).
        </p>
        <p>Preços e disponibilidade sujeitos a alteração.</p>
      </footer>
    </article>
  );
}
