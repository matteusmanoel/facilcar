import Link from "next/link";
import { prisma } from "@/lib/db";
import type { $Enums } from "@prisma/client";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function AdminLeadsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const status = typeof params.status === "string" ? params.status : undefined;
  const type = typeof params.tipo === "string" ? params.tipo : undefined;

  const leads = await prisma.lead.findMany({
    where: {
      ...(status && { status: status as $Enums.LeadStatus }),
      ...(type && { type: type as $Enums.LeadType }),
    },
    orderBy: { createdAt: "desc" },
    take: 100,
    include: { vehicle: { select: { title: true, slug: true } } },
  });

  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold">Leads</h1>
      <form method="get" className="mt-4 flex gap-2">
        <select name="status" defaultValue={status ?? ""} className="rounded border px-3 py-2">
          <option value="">Todos os status</option>
          <option value="NEW">Novo</option>
          <option value="IN_PROGRESS">Em progresso</option>
          <option value="CONTACTED">Contactado</option>
          <option value="QUALIFIED">Qualificado</option>
          <option value="WON">Ganho</option>
          <option value="LOST">Perdido</option>
        </select>
        <select name="tipo" defaultValue={type ?? ""} className="rounded border px-3 py-2">
          <option value="">Todos os tipos</option>
          <option value="CONTACT">Contato</option>
          <option value="VEHICLE_INTEREST">Interesse veículo</option>
          <option value="FINANCING">Financiamento</option>
          <option value="SELL_VEHICLE">Vender veículo</option>
        </select>
        <button type="submit" className="rounded bg-zinc-900 px-4 py-2 text-white hover:bg-zinc-800">
          Filtrar
        </button>
      </form>
      <div className="mt-4 overflow-x-auto rounded border">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50">
            <tr>
              <th className="p-2 text-left">Data</th>
              <th className="p-2 text-left">Nome</th>
              <th className="p-2 text-left">Telefone</th>
              <th className="p-2 text-left">Tipo</th>
              <th className="p-2 text-left">Status</th>
              <th className="p-2 text-left">Ações</th>
            </tr>
          </thead>
          <tbody>
            {leads.map((lead) => (
              <tr key={lead.id} className="border-t">
                <td className="p-2">{new Date(lead.createdAt).toLocaleString("pt-BR")}</td>
                <td className="p-2">{lead.name}</td>
                <td className="p-2">{lead.phone}</td>
                <td className="p-2">{lead.type}</td>
                <td className="p-2">{lead.status}</td>
                <td className="p-2">
                  <Link href={`/admin/leads/${lead.id}`} className="text-zinc-600 hover:underline">
                    Ver
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
