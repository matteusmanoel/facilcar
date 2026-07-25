import type { LeadStatus, LeadType } from "@prisma/client";
import { startOfDay, subDays, format } from "date-fns";
import { prisma } from "@/lib/db";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { listAdminLeads, parseDashboardDateParam } from "@/features/lead/server/queries";
import { LeadsClient } from "./LeadsClient";
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

function parseAssignee(value: string | undefined): string | null | undefined {
  if (!value || value === "all") return undefined;
  if (value === "none") return null;
  return value;
}

export default async function AdminLeadsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  await guardAdminSection("leads");
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

    const kanbanVehicles = await prisma.vehicle.findMany({
      where: { status: { in: ["PUBLISHED", "RESERVED", "DRAFT"] } },
      orderBy: { updatedAt: "desc" },
      take: 200,
      select: { id: true, title: true },
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
          <div className="flex items-center gap-2">
            <NewLeadDialog vehicles={kanbanVehicles} />
            <ViewTabs currentView="kanban" />
          </div>
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
  const assignee = parseAssignee(typeof params.responsavel === "string" ? params.responsavel : undefined);
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

  const [{ leads, totalCount }, sellers, vehicles] = await Promise.all([
    listAdminLeads({
      page,
      pageSize,
      status,
      type,
      search: q,
      from: fromD,
      to: toD,
      assignedToUserId: assignee,
    }),
    prisma.user.findMany({
      where: { isActive: true },
      orderBy: { name: "asc" },
      select: { id: true, name: true },
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

  const currentAssignee =
    assignee === null ? "none" : assignee === undefined ? undefined : assignee;

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
        currentStatus={status}
        currentType={type}
        currentAssignee={currentAssignee}
        sellers={sellers}
        currentPeriod={period}
        fromKey={
          typeof params.from === "string"
            ? params.from
            : period === "7d" || period === "30d"
              ? format(startOfDay(subDays(new Date(), period === "7d" ? 6 : 29)), "yyyy-MM-dd")
              : undefined
        }
        toKey={
          typeof params.to === "string"
            ? params.to
            : period === "7d" || period === "30d"
              ? format(startOfDay(new Date()), "yyyy-MM-dd")
              : undefined
        }
        initialSearch={q ?? ""}
      />
    </div>
  );
}
