import Link from "next/link";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { endOfDay, startOfDay, subDays } from "date-fns";
import { BookOpen, Car, FileText, Settings, Sparkles, TrendingUp, Users } from "lucide-react";
import { prisma } from "@/lib/db";
import { StatCard } from "@/components/admin/StatCard";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { DashboardCharts } from "@/components/admin/charts/DashboardCharts";
import { DashboardPeriodFilter } from "@/components/admin/DashboardPeriodFilter";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { canAccessSection } from "@/features/auth/rbac-config";
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
  const user = await guardAdminSection("dashboard");
  const params = await searchParams;
  const showLeads = canAccessSection(user.role, "leads");
  const showVehicles = canAccessSection(user.role, "veiculos");
  const isEditor = user.role === "EDITOR";

  const toDate = parseDashboardDateParam(params.to) ?? endOfDay(new Date());
  const fromDate = parseDashboardDateParam(params.from) ?? startOfDay(subDays(toDate, 29));

  const [
    vehiclesCount,
    leadsCount,
    newLeadsCount,
    financingNewCount,
    recentLeads,
    blogPostsCount,
    pagesCount,
    byPeriod,
    byStatus,
    bySource,
  ] = await Promise.all([
    showVehicles ? prisma.vehicle.count({ where: { status: "PUBLISHED" } }) : Promise.resolve(0),
    showLeads ? prisma.lead.count({ where: { deletedAt: null } }) : Promise.resolve(0),
    showLeads ? prisma.lead.count({ where: { status: "NEW", deletedAt: null } }) : Promise.resolve(0),
    showLeads
      ? prisma.lead.count({ where: { type: "FINANCING", status: "NEW", deletedAt: null } })
      : Promise.resolve(0),
    showLeads
      ? prisma.lead.findMany({
          where: { deletedAt: null },
          take: 10,
          orderBy: { createdAt: "desc" },
          include: { vehicle: { select: { title: true, slug: true } } },
        })
      : Promise.resolve([]),
    isEditor ? prisma.blogPost.count() : Promise.resolve(0),
    isEditor ? prisma.page.count() : Promise.resolve(0),
    showLeads ? getLeadsDailyCountsInRange(fromDate, toDate) : Promise.resolve([]),
    showLeads ? getLeadsByStatusInRange(fromDate, toDate) : Promise.resolve([]),
    showLeads ? getLeadsBySourceInRange(fromDate, toDate) : Promise.resolve([]),
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
          <h1 className="admin-page-title">Dashboard</h1>
          <p className="admin-page-subtitle">
            {isEditor ? "Conteúdo e configurações do site" : "Visão geral da operação"}
          </p>
        </div>
        {showLeads && <DashboardPeriodFilter from={fromDate} to={toDate} />}
      </div>

      {isEditor ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard
              title="Posts no blog"
              value={blogPostsCount}
              href="/admin/blog"
              linkLabel="Gerenciar blog"
              icon={BookOpen}
            />
            <StatCard
              title="Páginas institucionais"
              value={pagesCount}
              href="/admin/paginas"
              linkLabel="Gerenciar páginas"
              icon={FileText}
            />
            <StatCard
              title="Configurações"
              value="—"
              href="/admin/configuracoes"
              linkLabel="Abrir configurações"
              icon={Settings}
            />
          </div>

          <div className="admin-card">
            <h2 className="admin-section-title">Áreas de conteúdo</h2>
            <p className="mt-1 text-sm text-facil-muted">
              Você tem acesso ao blog, páginas e configurações do site. Métricas de leads e estoque ficam
              disponíveis para perfis comerciais.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <Link
                href="/admin/blog"
                className="rounded-lg border border-facil-border px-4 py-2 text-sm font-medium text-foreground hover:border-facil-orange hover:text-facil-orange"
              >
                Blog
              </Link>
              <Link
                href="/admin/paginas"
                className="rounded-lg border border-facil-border px-4 py-2 text-sm font-medium text-foreground hover:border-facil-orange hover:text-facil-orange"
              >
                Páginas
              </Link>
              <Link
                href="/admin/configuracoes"
                className="rounded-lg border border-facil-border px-4 py-2 text-sm font-medium text-foreground hover:border-facil-orange hover:text-facil-orange"
              >
                Configurações
              </Link>
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {showVehicles && (
              <StatCard
                title="Veículos publicados"
                value={vehiclesCount}
                href="/admin/veiculos"
                linkLabel="Gerenciar estoque"
                icon={Car}
              />
            )}
            {showLeads && (
              <>
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
              </>
            )}
          </div>

          {showLeads && (
            <>
              <DashboardCharts
                periodTitle={periodTitle}
                periodData={periodChartData}
                statusData={statusChartData}
                sourceData={sourceChartData}
              />

              <div>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="admin-section-title">Últimos leads</h2>
                  <Link href="/admin/leads" className="text-sm text-facil-orange hover:underline">
                    Ver todos →
                  </Link>
                </div>
                <div className="overflow-hidden rounded-xl border border-facil-border bg-facil-card shadow-sm">
                  <div className="hidden overflow-x-auto md:block">
                    <table className="w-full text-sm">
                      <thead className="border-b border-facil-border bg-facil-surface">
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
                            <td colSpan={6} className="py-8 text-center text-sm text-facil-muted">
                              Nenhum lead ainda.
                            </td>
                          </tr>
                        ) : (
                          recentLeads.map((lead) => (
                            <tr
                              key={lead.id}
                              className="border-t border-facil-border hover:bg-facil-surface/50"
                            >
                              <td className="admin-table-cell text-facil-muted">
                                {new Date(lead.createdAt).toLocaleDateString("pt-BR")}
                              </td>
                              <td className="admin-table-cell font-medium">
                                {lead.name}
                              </td>
                              <td className="admin-table-cell">
                                <StatusBadge status={lead.type} type="type" />
                              </td>
                              <td className="admin-table-cell">
                                <StatusBadge status={lead.status} />
                              </td>
                              <td className="admin-table-cell text-facil-muted">
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
                  <div className="divide-y divide-facil-border md:hidden">
                    {recentLeads.map((lead) => (
                      <Link
                        key={lead.id}
                        href={`/admin/leads/${lead.id}`}
                        className="flex items-center justify-between px-4 py-3 hover:bg-facil-surface/50"
                      >
                        <div>
                          <p className="text-sm font-medium text-foreground">{lead.name}</p>
                          <p className="text-xs text-facil-muted">
                            {new Date(lead.createdAt).toLocaleDateString("pt-BR")}
                          </p>
                        </div>
                        <StatusBadge status={lead.status} />
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
