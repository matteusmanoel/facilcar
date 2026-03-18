import Link from "next/link";
import { prisma } from "@/lib/db";

export default async function AdminDashboardPage() {
  const [vehiclesCount, leadsCount, newLeadsCount, recentLeads] = await Promise.all([
    prisma.vehicle.count({ where: { status: "PUBLISHED" } }),
    prisma.lead.count(),
    prisma.lead.count({ where: { status: "NEW" } }),
    prisma.lead.findMany({
      take: 10,
      orderBy: { createdAt: "desc" },
      include: { vehicle: { select: { title: true, slug: true } } },
    }),
  ]);

  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border bg-white p-4">
          <p className="text-sm text-zinc-500">Veículos publicados</p>
          <p className="text-2xl font-semibold">{vehiclesCount}</p>
          <Link href="/admin/veiculos" className="mt-2 text-sm text-zinc-600 hover:underline">
            Ver veículos
          </Link>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <p className="text-sm text-zinc-500">Total de leads</p>
          <p className="text-2xl font-semibold">{leadsCount}</p>
          <Link href="/admin/leads" className="mt-2 text-sm text-zinc-600 hover:underline">
            Ver leads
          </Link>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <p className="text-sm text-zinc-500">Leads novos</p>
          <p className="text-2xl font-semibold">{newLeadsCount}</p>
        </div>
      </div>
      <div className="mt-8">
        <h2 className="text-lg font-medium">Últimos leads</h2>
        <div className="mt-2 overflow-x-auto rounded border">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50">
              <tr>
                <th className="p-2 text-left">Data</th>
                <th className="p-2 text-left">Nome</th>
                <th className="p-2 text-left">Tipo</th>
                <th className="p-2 text-left">Status</th>
                <th className="p-2 text-left">Veículo</th>
                <th className="p-2 text-left">Ações</th>
              </tr>
            </thead>
            <tbody>
              {recentLeads.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-4 text-center text-zinc-500">
                    Nenhum lead ainda.
                  </td>
                </tr>
              ) : (
                recentLeads.map((lead) => (
                  <tr key={lead.id} className="border-t">
                    <td className="p-2">{new Date(lead.createdAt).toLocaleString("pt-BR")}</td>
                    <td className="p-2">{lead.name}</td>
                    <td className="p-2">{lead.type}</td>
                    <td className="p-2">{lead.status}</td>
                    <td className="p-2">
                      {lead.vehicle ? (
                        <Link href={`/estoque/${lead.vehicle.slug}`} className="hover:underline">
                          {lead.vehicle.title}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="p-2">
                      <Link href={`/admin/leads/${lead.id}`} className="text-zinc-600 hover:underline">
                        Ver
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
