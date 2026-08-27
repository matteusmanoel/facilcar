import { prisma } from "@/lib/db";
import type { Prisma } from "@prisma/client";
import type { LeadStatus, LeadType } from "@prisma/client";
import { eachDayOfInterval, endOfDay, format, startOfDay } from "date-fns";

const NOT_DELETED: Prisma.LeadWhereInput = { deletedAt: null };

export function parseDashboardDateParam(value: string | undefined): Date | undefined {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return undefined;
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function createdAtRangeFilter(
  from?: Date,
  to?: Date,
): Prisma.DateTimeFilter | undefined {
  if (!from && !to) return undefined;
  const filter: Prisma.DateTimeFilter = {};
  if (from) filter.gte = startOfDay(from);
  if (to) filter.lte = endOfDay(to);
  return filter;
}

/** Série diária de contagem de leads (inclusive) entre from e to. */
export async function getLeadsDailyCountsInRange(from: Date, to: Date) {
  const start = startOfDay(from);
  const end = endOfDay(to);
  const leads = await prisma.lead.findMany({
    where: { createdAt: { gte: start, lte: end }, ...NOT_DELETED },
    select: { createdAt: true },
    orderBy: { createdAt: "asc" },
  });

  const days = eachDayOfInterval({ start, end });
  const grouped: Record<string, number> = {};
  for (const day of days) {
    grouped[format(day, "yyyy-MM-dd")] = 0;
  }

  for (const lead of leads) {
    const key = format(startOfDay(lead.createdAt), "yyyy-MM-dd");
    if (key in grouped) grouped[key]++;
  }

  return Object.entries(grouped).map(([date, count]) => ({ date, count }));
}

export async function getLeadsByStatusInRange(from?: Date, to?: Date) {
  const ca = createdAtRangeFilter(from, to);
  const result = await prisma.lead.groupBy({
    by: ["status"],
    where: ca ? { createdAt: ca, ...NOT_DELETED } : NOT_DELETED,
    _count: { id: true },
    orderBy: { _count: { id: "desc" } },
  });

  const LABELS: Record<string, string> = {
    NEW: "Novo",
    IN_PROGRESS: "Em progresso",
    CONTACTED: "Contactado",
    QUALIFIED: "Qualificado",
    WON: "Ganho",
    LOST: "Perdido",
    SPAM: "Spam",
  };

  return result.map((r) => ({
    status: r.status,
    label: LABELS[r.status] ?? r.status,
    count: r._count.id,
  }));
}

export async function getLeadsBySourceInRange(from?: Date, to?: Date) {
  const ca = createdAtRangeFilter(from, to);
  const result = await prisma.lead.groupBy({
    by: ["source"],
    where: ca ? { createdAt: ca, ...NOT_DELETED } : NOT_DELETED,
    _count: { id: true },
    orderBy: { _count: { id: "desc" } },
  });

  const LABELS: Record<string, string> = {
    HOME: "Página inicial",
    CATALOG: "Catálogo",
    VEHICLE_PAGE: "Página do veículo",
    CONTACT_PAGE: "Contato",
    FINANCING_PAGE: "Financiamento",
    SELL_PAGE: "Vender veículo",
    BLOG: "Blog",
    UNKNOWN: "Desconhecido",
  };

  return result.map((r) => ({
    source: r.source,
    label: LABELS[r.source] ?? r.source,
    count: r._count.id,
  }));
}

const ADMIN_LEAD_SELECT = {
  id: true,
  name: true,
  phone: true,
  email: true,
  type: true,
  status: true,
  source: true,
  message: true,
  internalNote: true,
  temperature: true,
  createdAt: true,
  assignedToUser: { select: { id: true, name: true } },
  vehicle: { select: { title: true, slug: true } },
} as const;

export type AdminLeadRow = Prisma.LeadGetPayload<{ select: typeof ADMIN_LEAD_SELECT }>;

export type AdminLeadFilterInput = {
  statuses?: LeadStatus[];
  types?: LeadType[];
  assignees?: string[];
  search?: string;
  from?: Date;
  to?: Date;
};

export function buildAdminLeadWhere(opts: AdminLeadFilterInput): Prisma.LeadWhereInput {
  const where: Prisma.LeadWhereInput = { ...NOT_DELETED };

  if (opts.statuses?.length) where.status = { in: opts.statuses };
  if (opts.types?.length) where.type = { in: opts.types };

  if (opts.assignees?.length) {
    const ids = opts.assignees.filter((a) => a !== "none");
    const includeNone = opts.assignees.includes("none");
    if (includeNone && ids.length) {
      where.OR = [
        { assignedToUserId: null },
        { assignedToUserId: { in: ids } },
      ];
    } else if (includeNone) {
      where.assignedToUserId = null;
    } else if (ids.length) {
      where.assignedToUserId = { in: ids };
    }
  }

  const ca = createdAtRangeFilter(opts.from, opts.to);
  if (ca) where.createdAt = ca;

  const q = opts.search?.trim();
  if (q) {
    const searchOr: Prisma.LeadWhereInput[] = [
      { name: { contains: q, mode: "insensitive" } },
      { phone: { contains: q } },
      { email: { contains: q, mode: "insensitive" } },
      { vehicle: { title: { contains: q, mode: "insensitive" } } },
    ];
    if (where.OR) {
      where.AND = [{ OR: where.OR }, { OR: searchOr }];
      delete where.OR;
    } else {
      where.OR = searchOr;
    }
  }

  return where;
}

export async function listAdminLeads(opts: {
  page: number;
  pageSize: number;
  statuses?: LeadStatus[];
  types?: LeadType[];
  search?: string;
  from?: Date;
  to?: Date;
  assignees?: string[];
}) {
  const where = buildAdminLeadWhere({
    statuses: opts.statuses,
    types: opts.types,
    assignees: opts.assignees,
    search: opts.search,
    from: opts.from,
    to: opts.to,
  });

  const skip = (Math.max(1, opts.page) - 1) * opts.pageSize;

  const [totalCount, leads] = await Promise.all([
    prisma.lead.count({ where }),
    prisma.lead.findMany({
      where,
      orderBy: { createdAt: "desc" },
      skip,
      take: opts.pageSize,
      select: ADMIN_LEAD_SELECT,
    }),
  ]);

  return { leads, totalCount };
}

export async function listAdminLeadsForKanban(opts: AdminLeadFilterInput & { take?: number }) {
  const where = buildAdminLeadWhere(opts);
  return prisma.lead.findMany({
    where,
    orderBy: { createdAt: "desc" },
    take: opts.take ?? 300,
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
}

export async function getLeadsByPeriod(days: number) {
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

  const leads = await prisma.lead.findMany({
    where: { createdAt: { gte: since }, ...NOT_DELETED },
    select: { createdAt: true },
    orderBy: { createdAt: "asc" },
  });

  // Group by date (YYYY-MM-DD)
  const grouped: Record<string, number> = {};
  for (let i = 0; i < days; i++) {
    const d = new Date(Date.now() - (days - 1 - i) * 24 * 60 * 60 * 1000);
    const key = d.toISOString().slice(0, 10);
    grouped[key] = 0;
  }

  for (const lead of leads) {
    const key = lead.createdAt.toISOString().slice(0, 10);
    if (key in grouped) grouped[key]++;
  }

  return Object.entries(grouped).map(([date, count]) => ({ date, count }));
}

export async function getLeadsByStatus() {
  const result = await prisma.lead.groupBy({
    by: ["status"],
    where: NOT_DELETED,
    _count: { id: true },
    orderBy: { _count: { id: "desc" } },
  });

  const LABELS: Record<string, string> = {
    NEW: "Novo",
    IN_PROGRESS: "Em progresso",
    CONTACTED: "Contactado",
    QUALIFIED: "Qualificado",
    WON: "Ganho",
    LOST: "Perdido",
    SPAM: "Spam",
  };

  return result.map((r) => ({
    status: r.status,
    label: LABELS[r.status] ?? r.status,
    count: r._count.id,
  }));
}

export async function getLeadsBySource() {
  const result = await prisma.lead.groupBy({
    by: ["source"],
    where: NOT_DELETED,
    _count: { id: true },
    orderBy: { _count: { id: "desc" } },
  });

  const LABELS: Record<string, string> = {
    HOME: "Página inicial",
    CATALOG: "Catálogo",
    VEHICLE_PAGE: "Página do veículo",
    CONTACT_PAGE: "Contato",
    FINANCING_PAGE: "Financiamento",
    SELL_PAGE: "Vender veículo",
    BLOG: "Blog",
    UNKNOWN: "Desconhecido",
  };

  return result.map((r) => ({
    source: r.source,
    label: LABELS[r.source] ?? r.source,
    count: r._count.id,
  }));
}
