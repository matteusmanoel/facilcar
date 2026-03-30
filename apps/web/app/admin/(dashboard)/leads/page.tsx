import Link from "next/link";
import type { LeadStatus, LeadType } from "@prisma/client";
import { startOfDay, subDays } from "date-fns";
import { prisma } from "@/lib/db";
import { listAdminLeads, parseDashboardDateParam } from "@/features/lead/server/queries";
import { LeadsClient } from "./LeadsClient";
import { KanbanBoardLoader } from "@/components/admin/Kanban/KanbanBoardLoader";
import { ViewTabs } from "./ViewTabs";

const LEAD_STATUSES: LeadStatus[] = [
  "NEW",
  "IN_PROGRESS",
  "CONTACTED",
  "QUALIFIED",
  "WON",
  "LOST",
  "SPAM",
];

const LEAD_TYPES: LeadType[] = [
  "CONTACT",
  "VEHICLE_INTEREST",
  "FINANCING",
  "SELL_VEHICLE",
];

type SearchParams = { [key: string]: string | string[] | undefined };

function parseLeadStatus(value: string | undefined): LeadStatus | undefined {
  if (!value) return undefined;
  return LEAD_STATUSES.includes(value as LeadStatus) ? (value as LeadStatus) : undefined;
}

function parseLeadType(value: string | undefined): LeadType | undefined {
  if (!value) return undefined;
  return LEAD_TYPES.includes(value as LeadType) ? (value as LeadType) : undefined;
}

export default async function AdminLeadsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const view = params.view === "kanban" ? "kanban" : "lista";

  if (view === "kanban") {
    const leads = await prisma.lead.findMany({
      where: {
        status: { in: ["NEW", "IN_PROGRESS", "CONTACTED", "QUALIFIED", "WON", "LOST"] },
      },
      orderBy: { createdAt: "desc" },
      take: 300,
      select: {
        id: true,
        name: true,
        phone: true,
        type: true,
        status: true,
        createdAt: true,
        vehicle: { select: { title: true } },
      },
    });

    return (
      <div className="admin-page admin-section">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Leads & CRM</h1>
            <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
              Arraste os cards entre colunas para atualizar o status
            </p>
          </div>
          <ViewTabs currentView="kanban" />
        </div>
        <KanbanBoardLoader initialLeads={leads} />
      </div>
    );
  }

  const page = Math.max(1, parseInt(String(params.page ?? "1"), 10) || 1);
  const pageSize = Math.min(100, Math.max(5, parseInt(String(params.pageSize ?? "20"), 10) || 20));
  const q = typeof params.q === "string" ? params.q : undefined;
  const status = parseLeadStatus(typeof params.status === "string" ? params.status : undefined);
  const type = parseLeadType(typeof params.tipo === "string" ? params.tipo : undefined);
  const period = typeof params.periodo === "string" ? params.periodo : "all";

  let fromD: Date | undefined;
  let toD: Date | undefined;
  const customFrom = parseDashboardDateParam(typeof params.from === "string" ? params.from : undefined);
  const customTo = parseDashboardDateParam(typeof params.to === "string" ? params.to : undefined);

  if (customFrom && customTo) {
    fromD = customFrom;
    toD = customTo;
  } else if (period === "7d") {
    toD = new Date();
    fromD = startOfDay(subDays(toD, 6));
  } else if (period === "30d") {
    toD = new Date();
    fromD = startOfDay(subDays(toD, 29));
  }

  const { leads, totalCount } = await listAdminLeads({
    page,
    pageSize,
    status,
    type,
    search: q,
    from: fromD,
    to: toD,
  });

  const serializableLeads = leads.map((l) => ({
    ...l,
    createdAt: l.createdAt.toISOString(),
  }));

  return (
    <div className="admin-page admin-section">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Leads & CRM</h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            Gerencie e acompanhe todos os contatos
          </p>
        </div>
        <ViewTabs currentView="lista" />
      </div>

      <LeadsClient
        leads={serializableLeads}
        totalCount={totalCount}
        page={page}
        pageSize={pageSize}
        currentStatus={status}
        currentType={type}
        currentPeriod={period}
        fromKey={
          customFrom && customTo && typeof params.from === "string" ? params.from : undefined
        }
        toKey={customFrom && customTo && typeof params.to === "string" ? params.to : undefined}
        initialSearch={q ?? ""}
      />
    </div>
  );
}
