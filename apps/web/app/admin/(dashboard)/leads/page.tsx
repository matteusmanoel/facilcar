import type { LeadStatus, LeadType } from "@prisma/client";
import { startOfDay, subDays, format } from "date-fns";
import { prisma } from "@/lib/db";
import { guardAdminSection } from "@/features/auth/server/rbac";
import {
  listAdminLeads,
  listAdminLeadsForKanban,
  parseDashboardDateParam,
} from "@/features/lead/server/queries";
import { parseCsvParam, parseEnumCsv } from "@/lib/query-filters";
import { LeadsClient } from "./LeadsClient";
import { LeadsFilterToolbar } from "./LeadsFilterToolbar";
import { KanbanBoardLoader } from "@/components/admin/Kanban/KanbanBoardLoader";
import { ViewTabs } from "./ViewTabs";
import { NewLeadDialog } from "./NewLeadDialog";

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
  "REFINANCING",
  "TRADE_IN",
  "CONSIGNMENT",
  "THIRD_PARTY_FINANCING",
];

type SearchParams = { [key: string]: string | string[] | undefined };

function parseDateRange(
  params: SearchParams,
  period: string,
): { fromD?: Date; toD?: Date; fromKey?: string; toKey?: string } {
  const customFrom = parseDashboardDateParam(
    typeof params.from === "string" ? params.from : undefined,
  );
  const customTo = parseDashboardDateParam(
    typeof params.to === "string" ? params.to : undefined,
  );

  if (customFrom && customTo) {
    return {
      fromD: customFrom,
      toD: customTo,
      fromKey: typeof params.from === "string" ? params.from : undefined,
      toKey: typeof params.to === "string" ? params.to : undefined,
    };
  }

  if (period === "7d") {
    const toD = new Date();
    const fromD = startOfDay(subDays(toD, 6));
    return {
      fromD,
      toD,
      fromKey: format(fromD, "yyyy-MM-dd"),
      toKey: format(startOfDay(toD), "yyyy-MM-dd"),
    };
  }

  if (period === "30d") {
    const toD = new Date();
    const fromD = startOfDay(subDays(toD, 29));
    return {
      fromD,
      toD,
      fromKey: format(fromD, "yyyy-MM-dd"),
      toKey: format(startOfDay(toD), "yyyy-MM-dd"),
    };
  }

  return {};
}

export default async function AdminLeadsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  await guardAdminSection("leads");
  const params = await searchParams;
  const view = params.view === "kanban" ? "kanban" : "lista";

  const q = typeof params.q === "string" ? params.q : undefined;
  const statusParam = typeof params.status === "string" ? params.status : undefined;
  const typeParam = typeof params.tipo === "string" ? params.tipo : undefined;
  const assigneeParam = typeof params.responsavel === "string" ? params.responsavel : undefined;
  const period = typeof params.periodo === "string" ? params.periodo : "all";

  const statuses = parseEnumCsv(statusParam, LEAD_STATUSES);
  const types = parseEnumCsv(typeParam, LEAD_TYPES);
  const assignees = parseCsvParam(assigneeParam);

  const { fromD, toD, fromKey, toKey } = parseDateRange(params, period);

  const sellers = await prisma.user.findMany({
    where: { isActive: true },
    orderBy: { name: "asc" },
    select: { id: true, name: true },
  });

  if (view === "kanban") {
    const [leads, kanbanVehicles] = await Promise.all([
      listAdminLeadsForKanban({
        statuses,
        types,
        assignees,
        search: q,
        from: fromD,
        to: toD,
      }),
      prisma.vehicle.findMany({
        where: { status: { in: ["PUBLISHED", "RESERVED", "DRAFT"] } },
        orderBy: { updatedAt: "desc" },
        take: 200,
        select: { id: true, title: true },
      }),
    ]);

    return (
      <div className="admin-page admin-section">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Leads & CRM</h1>
            <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
              Arraste os cards entre colunas para atualizar o status
            </p>
          </div>
          <div className="flex items-center gap-2">
            <NewLeadDialog vehicles={kanbanVehicles} />
            <ViewTabs currentView="kanban" />
          </div>
        </div>

        <LeadsFilterToolbar
          sellers={sellers}
          statuses={statuses}
          types={types}
          assignees={assignees}
          currentPeriod={period}
          fromKey={fromKey}
          toKey={toKey}
          initialSearch={q ?? ""}
          totalCount={leads.length}
          preserveView
        />

        <KanbanBoardLoader initialLeads={leads} />
      </div>
    );
  }

  const page = Math.max(1, parseInt(String(params.page ?? "1"), 10) || 1);
  const pageSize = Math.min(100, Math.max(5, parseInt(String(params.pageSize ?? "20"), 10) || 20));

  const [{ leads, totalCount }, vehicles] = await Promise.all([
    listAdminLeads({
      page,
      pageSize,
      statuses,
      types,
      assignees,
      search: q,
      from: fromD,
      to: toD,
    }),
    prisma.vehicle.findMany({
      where: { status: { in: ["PUBLISHED", "RESERVED", "DRAFT"] } },
      orderBy: { updatedAt: "desc" },
      take: 200,
      select: { id: true, title: true },
    }),
  ]);

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
        <div className="flex items-center gap-2">
          <NewLeadDialog vehicles={vehicles} />
          <ViewTabs currentView="lista" />
        </div>
      </div>

      <LeadsClient
        leads={serializableLeads}
        totalCount={totalCount}
        page={page}
        pageSize={pageSize}
        statuses={statuses}
        types={types}
        assignees={assignees}
        sellers={sellers}
        currentPeriod={period}
        fromKey={fromKey}
        toKey={toKey}
        initialSearch={q ?? ""}
      />
    </div>
  );
}
