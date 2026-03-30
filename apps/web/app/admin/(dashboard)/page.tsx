import Link from "next/link";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { endOfDay, startOfDay, subDays } from "date-fns";
import { Car, Users, Sparkles, TrendingUp } from "lucide-react";
import { prisma } from "@/lib/db";
import { StatCard } from "@/components/admin/StatCard";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { DashboardCharts } from "@/components/admin/charts/DashboardCharts";
import { DashboardPeriodFilter } from "@/components/admin/DashboardPeriodFilter";
import {
  getLeadsDailyCountsInRange,
  getLeadsByStatusInRange,
  getLeadsBySourceInRange,
  parseDashboardDateParam,
} from "@/features/lead/server/queries";

export default async function AdminDashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ from?: string; to?: string }>;
}) {
  const params = await searchParams;

  const toDate = parseDashboardDateParam(params.to) ?? endOfDay(new Date());
  const fromDate = parseDashboardDateParam(params.from) ?? startOfDay(subDays(toDate, 29));

  const [
    vehiclesCount,
    leadsCount,
    newLeadsCount,
    financingNewCount,
    recentLeads,
    byPeriod,
    byStatus,
    bySource,
  ] = await Promise.all([
    prisma.vehicle.count({ where: { status: "PUBLISHED" } }),
    prisma.lead.count(),
    prisma.lead.count({ where: { status: "NEW" } }),
    prisma.lead.count({ where: { type: "FINANCING", status: "NEW" } }),
    prisma.lead.findMany({
      take: 10,
      orderBy: { createdAt: "desc" },
      include: { vehicle: { select: { title: true, slug: true } } },
    }),
    getLeadsDailyCountsInRange(fromDate, toDate),
    getLeadsByStatusInRange(fromDate, toDate),
    getLeadsBySourceInRange(fromDate, toDate),
  ]);

  const periodChartData = byPeriod.map((d) => ({
    label: new Date(d.date + "T00:00:00").toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
    }),
    value: d.count,
  }));

  const statusChartData = byStatus.map((d) => ({ label: d.label, value: d.count }));
  const sourceChartData = bySource.map((d) => ({ label: d.label, value: d.count }));

  const periodTitle = `Leads — ${format(fromDate, "dd/MM/yyyy", { locale: ptBR })} a ${format(toDate, "dd/MM/yyyy", { locale: ptBR })}`;

  return (
    <div className="admin-page admin-section">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Dashboard</h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Visão geral da operação</p>
        </div>
        <DashboardPeriodFilter from={fromDate} to={toDate} />
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Veículos publicados"
          value={vehiclesCount}
          href="/admin/veiculos"
          linkLabel="Gerenciar estoque"
          icon={Car}
        />
        <StatCard
          title="Total de leads"
          value={leadsCount}
          href="/admin/leads"
          linkLabel="Ver todos os leads"
          icon={Users}
        />
        <StatCard
          title="Leads novos"
          value={newLeadsCount}
          href="/admin/leads?status=NEW"
          linkLabel="Ver novos"
          icon={Sparkles}
          variant="highlight"
        />
        <StatCard
          title="Simulações pendentes"
          value={financingNewCount}
          href="/admin/leads?tipo=FINANCING&status=NEW"
          linkLabel="Atender agora"
          icon={TrendingUp}
          variant={financingNewCount > 0 ? "warning" : "default"}
        />
      </div>

      {/* Charts */}
      <DashboardCharts
        periodTitle={periodTitle}
        periodData={periodChartData}
        statusData={statusChartData}
        sourceData={sourceChartData}
      />

      {/* Recent leads */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">Últimos leads</h2>
          <Link href="/admin/leads" className="text-sm text-facil-orange hover:underline">
            Ver todos →
          </Link>
        </div>
        <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-100 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-800/50">
                <tr>
                  <th className="admin-table-header">Data</th>
                  <th className="admin-table-header">Nome</th>
                  <th className="admin-table-header">Tipo</th>
                  <th className="admin-table-header">Status</th>
                  <th className="admin-table-header">Veículo</th>
                  <th className="admin-table-header">Ações</th>
                </tr>
              </thead>
              <tbody>
                {recentLeads.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-sm text-zinc-400">
                      Nenhum lead ainda.
                    </td>
                  </tr>
                ) : (
                  recentLeads.map((lead) => (
                    <tr
                      key={lead.id}
                      className="border-t border-zinc-100 hover:bg-zinc-50/50 dark:border-zinc-800 dark:hover:bg-zinc-800/40"
                    >
                      <td className="admin-table-cell text-zinc-500 dark:text-zinc-400">
                        {new Date(lead.createdAt).toLocaleDateString("pt-BR")}
                      </td>
                      <td className="admin-table-cell font-medium text-zinc-900 dark:text-zinc-100">
                        {lead.name}
                      </td>
                      <td className="admin-table-cell">
                        <StatusBadge status={lead.type} type="type" />
                      </td>
                      <td className="admin-table-cell">
                        <StatusBadge status={lead.status} />
                      </td>
                      <td className="admin-table-cell text-zinc-500 dark:text-zinc-400">
                        {lead.vehicle ? (
                          <span className="line-clamp-1">{lead.vehicle.title}</span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="admin-table-cell">
                        <Link
                          href={`/admin/leads/${lead.id}`}
                          className="font-medium text-facil-orange hover:underline"
                        >
                          Ver
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {/* Mobile */}
          <div className="divide-y divide-zinc-100 md:hidden dark:divide-zinc-800">
            {recentLeads.map((lead) => (
              <Link
                key={lead.id}
                href={`/admin/leads/${lead.id}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
              >
                <div>
                  <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{lead.name}</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    {new Date(lead.createdAt).toLocaleDateString("pt-BR")}
                  </p>
                </div>
                <StatusBadge status={lead.status} />
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
