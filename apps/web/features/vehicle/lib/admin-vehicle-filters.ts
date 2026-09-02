import type { FuelType, Prisma, Transmission, VehicleCommercialHistory, VehicleStatus, VehicleStockType, VehicleType } from "@prisma/client";
import { parseCsvParam, parseEnumCsv } from "@/lib/query-filters";

export const PRINT_STOCK_LIMIT = 500;

export const VEHICLE_STATUSES: VehicleStatus[] = [
  "DRAFT",
  "PUBLISHED",
  "RESERVED",
  "SOLD",
  "ARCHIVED",
];

export const VEHICLE_TYPES: VehicleType[] = ["CAR", "MOTORCYCLE", "UTILITY", "OTHER"];
export const VEHICLE_STOCK_TYPES: VehicleStockType[] = ["OWNED", "CONSIGNED"];
export const VEHICLE_COMMERCIAL_HISTORIES: VehicleCommercialHistory[] = [
  "CLEAN",
  "AUCTION",
  "RECOVERED_CLAIM",
  "AUCTION_AND_RECOVERED_CLAIM",
];

export const FUEL_TYPES: FuelType[] = [
  "GASOLINE",
  "ETHANOL",
  "FLEX",
  "DIESEL",
  "ELECTRIC",
  "HYBRID",
  "OTHER",
];

export const TRANSMISSIONS: Transmission[] = ["MANUAL", "AUTOMATIC", "AUTOMATED", "CVT", "OTHER"];

export type AdminVehicleFilterInput = {
  statuses?: VehicleStatus[];
  search?: string;
  brandIds?: string[];
  types?: VehicleType[];
  stockTypes?: VehicleStockType[];
  commercialHistories?: VehicleCommercialHistory[];
  featuredValues?: boolean[];
  fuelTypes?: FuelType[];
  transmissions?: Transmission[];
  priceMin?: number;
  priceMax?: number;
  yearMin?: number;
  yearMax?: number;
  hasPhotoValues?: boolean[];
  ids?: string[];
};

export type SearchParamsRecord = { [key: string]: string | string[] | undefined };

export type ParsedAdminVehicleListParams = AdminVehicleFilterInput & {
  page: number;
  pageSize: number;
};

function firstString(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return typeof value === "string" ? value : undefined;
}

function parseOptionalNumber(value: string | undefined): number | undefined {
  if (!value?.trim()) return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function parseBooleanCsv(value: string | undefined): boolean[] {
  return parseCsvParam(value)
    .filter((v) => v === "true" || v === "false")
    .map((v) => v === "true");
}

export function parseAdminVehicleListParams(
  params: SearchParamsRecord,
): ParsedAdminVehicleListParams {
  const page = Math.max(1, parseInt(String(firstString(params.page) ?? "1"), 10) || 1);
  const pageSize = Math.min(
    100,
    Math.max(5, parseInt(String(firstString(params.pageSize) ?? "20"), 10) || 20),
  );

  return {
    page,
    pageSize,
    search: firstString(params.q),
    statuses: parseEnumCsv(firstString(params.status), VEHICLE_STATUSES),
    brandIds: parseCsvParam(firstString(params.brandId)),
    types: parseEnumCsv(firstString(params.type), VEHICLE_TYPES),
    stockTypes: parseEnumCsv(firstString(params.stockType), VEHICLE_STOCK_TYPES),
    commercialHistories: parseEnumCsv(firstString(params.history), VEHICLE_COMMERCIAL_HISTORIES),
    featuredValues: parseBooleanCsv(firstString(params.featured)),
    hasPhotoValues: parseBooleanCsv(firstString(params.hasPhoto)),
    fuelTypes: parseEnumCsv(firstString(params.fuelType), FUEL_TYPES),
    transmissions: parseEnumCsv(firstString(params.transmission), TRANSMISSIONS),
    priceMin: parseOptionalNumber(firstString(params.priceMin)),
    priceMax: parseOptionalNumber(firstString(params.priceMax)),
    yearMin: parseOptionalNumber(firstString(params.yearMin)),
    yearMax: parseOptionalNumber(firstString(params.yearMax)),
    ids: parseCsvParam(firstString(params.ids)),
  };
}

/** Selection (`ids`) wins and may include non-published vehicles. Otherwise default to PUBLISHED. */
export function applyPrintListDefaults(opts: AdminVehicleFilterInput): AdminVehicleFilterInput {
  if (opts.ids?.length) {
    return { ids: opts.ids };
  }
  return {
    ...opts,
    statuses: opts.statuses?.length ? opts.statuses : ["PUBLISHED"],
  };
}

export function buildAdminVehicleWhere(opts: AdminVehicleFilterInput): Prisma.VehicleWhereInput {
  const where: Prisma.VehicleWhereInput = {};

  if (opts.ids?.length) {
    where.id = { in: opts.ids };
    return where;
  }

  if (opts.statuses?.length) where.status = { in: opts.statuses };
  if (opts.brandIds?.length) where.brandId = { in: opts.brandIds };
  if (opts.types?.length) where.type = { in: opts.types };
  if (opts.stockTypes?.length) where.stockType = { in: opts.stockTypes };
  if (opts.commercialHistories?.length) where.commercialHistory = { in: opts.commercialHistories };
  if (opts.fuelTypes?.length) where.fuelType = { in: opts.fuelTypes };
  if (opts.transmissions?.length) where.transmission = { in: opts.transmissions };

  if (opts.featuredValues?.length === 1) {
    where.featured = opts.featuredValues[0];
  }

  if (opts.hasPhotoValues?.length === 1) {
    where.images = opts.hasPhotoValues[0] ? { some: {} } : { none: {} };
  }

  if (opts.priceMin != null || opts.priceMax != null) {
    where.priceCash = {
      ...(opts.priceMin != null ? { gte: opts.priceMin } : {}),
      ...(opts.priceMax != null ? { lte: opts.priceMax } : {}),
    };
  }

  if (opts.yearMin != null || opts.yearMax != null) {
    where.yearModel = {
      ...(opts.yearMin != null ? { gte: opts.yearMin } : {}),
      ...(opts.yearMax != null ? { lte: opts.yearMax } : {}),
    };
  }

  const q = opts.search?.trim();
  if (q) {
    where.OR = [
      { title: { contains: q, mode: "insensitive" } },
      { model: { contains: q, mode: "insensitive" } },
      { slug: { contains: q, mode: "insensitive" } },
      { plate: { contains: q, mode: "insensitive" } },
      { brand: { name: { contains: q, mode: "insensitive" } } },
    ];
  }

  return where;
}
