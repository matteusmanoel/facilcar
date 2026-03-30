import { prisma } from "@/lib/db";
import type { Prisma } from "@prisma/client";
import type { LeadStatus, LeadType } from "@prisma/client";
import { eachDayOfInterval, endOfDay, format, startOfDay } from "date-fns";

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
    where: { createdAt: { gte: start, lte: end } },
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
    where: ca ? { createdAt: ca } : undefined,
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
    where: ca ? { createdAt: ca } : undefined,
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
  createdAt: true,
  vehicle: { select: { title: true, slug: true } },
} as const;

export type AdminLeadRow = Prisma.LeadGetPayload<{ select: typeof ADMIN_LEAD_SELECT }>;

export async function listAdminLeads(opts: {
  page: number;
  pageSize: number;
  status?: LeadStatus;
  type?: LeadType;
  search?: string;
  from?: Date;
  to?: Date;
}) {
  const where: Prisma.LeadWhereInput = {};
  if (opts.status) where.status = opts.status;
  if (opts.type) where.type = opts.type;
  const ca = createdAtRangeFilter(opts.from, opts.to);
  if (ca) where.createdAt = ca;

  const q = opts.search?.trim();
  if (q) {
    where.OR = [
      { name: { contains: q, mode: "insensitive" } },
      { phone: { contains: q } },
      { email: { contains: q, mode: "insensitive" } },
      { vehicle: { title: { contains: q, mode: "insensitive" } } },
    ];
  }

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

export async function getLeadsByPeriod(days: number) {
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000);

  const leads = await prisma.lead.findMany({
    where: { createdAt: { gte: since } },
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
