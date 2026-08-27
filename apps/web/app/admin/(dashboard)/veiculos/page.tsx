import Link from "next/link";
import { Plus } from "lucide-react";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { canWriteVehicles } from "@/features/auth/rbac-config";
import { getBrandsForFilter } from "@/features/catalog/server/queries";
import { listAdminVehicles } from "@/features/vehicle/server/queries";
import { parseCsvParam, parseEnumCsv } from "@/lib/query-filters";
import { Button } from "@/components/ui/button";
import { VehiclesClient } from "./VehiclesClient";

import type { FuelType, Transmission, VehicleStatus, VehicleType } from "@prisma/client";

const VEHICLE_STATUSES: VehicleStatus[] = [
  "DRAFT",
  "PUBLISHED",
  "RESERVED",
  "SOLD",
  "ARCHIVED",
];

const VEHICLE_TYPES: VehicleType[] = ["CAR", "MOTORCYCLE", "UTILITY", "OTHER"];
const FUEL_TYPES: FuelType[] = [
  "GASOLINE",
  "ETHANOL",
  "FLEX",
  "DIESEL",
  "ELECTRIC",
  "HYBRID",
  "OTHER",
];
const TRANSMISSIONS: Transmission[] = ["MANUAL", "AUTOMATIC", "AUTOMATED", "CVT", "OTHER"];

type SearchParams = { [key: string]: string | string[] | undefined };

function parseOptionalNumber(value: string | undefined): number | undefined {
  if (!value?.trim()) return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function parseFeaturedCsv(value: string | undefined): boolean[] {
  return parseCsvParam(value)
    .filter((v) => v === "true" || v === "false")
    .map((v) => v === "true");
}

export default async function AdminVeiculosPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const user = await guardAdminSection("veiculos");
  const canWrite = canWriteVehicles(user.role);
  const params = await searchParams;
  const page = Math.max(1, parseInt(String(params.page ?? "1"), 10) || 1);
  const pageSize = Math.min(100, Math.max(5, parseInt(String(params.pageSize ?? "20"), 10) || 20));
  const q = typeof params.q === "string" ? params.q : undefined;

  const statusParam = typeof params.status === "string" ? params.status : undefined;
  const brandParam = typeof params.brandId === "string" ? params.brandId : undefined;
  const typeParam = typeof params.type === "string" ? params.type : undefined;
  const featuredParam = typeof params.featured === "string" ? params.featured : undefined;
  const fuelParam = typeof params.fuelType === "string" ? params.fuelType : undefined;
  const transmissionParam = typeof params.transmission === "string" ? params.transmission : undefined;

  const statuses = parseEnumCsv(statusParam, VEHICLE_STATUSES);
  const brandIds = parseCsvParam(brandParam);
  const types = parseEnumCsv(typeParam, VEHICLE_TYPES);
  const featuredValues = parseFeaturedCsv(featuredParam);
  const fuelTypes = parseEnumCsv(fuelParam, FUEL_TYPES);
  const transmissions = parseEnumCsv(transmissionParam, TRANSMISSIONS);

  const priceMin = parseOptionalNumber(typeof params.priceMin === "string" ? params.priceMin : undefined);
  const priceMax = parseOptionalNumber(typeof params.priceMax === "string" ? params.priceMax : undefined);
  const yearMin = parseOptionalNumber(typeof params.yearMin === "string" ? params.yearMin : undefined);
  const yearMax = parseOptionalNumber(typeof params.yearMax === "string" ? params.yearMax : undefined);

  const [{ vehicles, totalCount }, brands] = await Promise.all([
    listAdminVehicles({
      page,
      pageSize,
      statuses,
      search: q,
      brandIds,
      types,
      featuredValues,
      fuelTypes,
      transmissions,
      priceMin,
      priceMax,
      yearMin,
      yearMax,
    }),
    getBrandsForFilter(),
  ]);

  const serializedVehicles = vehicles.map((vehicle) => ({
    id: vehicle.id,
    slug: vehicle.slug,
    title: vehicle.title,
    status: vehicle.status,
    priceCash: vehicle.priceCash != null ? Number(vehicle.priceCash) : null,
    brand: vehicle.brand,
    images: vehicle.images,
  }));

  return (
    <div className="admin-page admin-section">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="admin-page-title">Veículos</h1>
          <p className="admin-page-subtitle">Gerencie o estoque da loja</p>
        </div>
        {canWrite && (
          <Link href="/admin/veiculos/novo">
            <Button variant="primary" size="sm">
              <Plus className="h-4 w-4 mr-1" />
              Novo veículo
            </Button>
          </Link>
        )}
      </div>

      <VehiclesClient
        vehicles={serializedVehicles}
        totalCount={totalCount}
        page={page}
        pageSize={pageSize}
        brands={brands}
        filters={{
          statuses,
          brandIds,
          types,
          featuredValues,
          fuelTypes,
          transmissions,
          priceMin,
          priceMax,
          yearMin,
          yearMax,
        }}
        initialSearch={q ?? ""}
        canWrite={canWrite}
      />
    </div>
  );
}
