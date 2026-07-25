import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { canWriteVehicles } from "@/features/auth/rbac-config";
import { listAdminVehicles } from "@/features/vehicle/server/queries";
import { Button } from "@/components/ui/button";
import { VehiclesClient } from "./VehiclesClient";

import type { VehicleStatus } from "@prisma/client";

const VEHICLE_STATUSES: VehicleStatus[] = [
  "DRAFT",
  "PUBLISHED",
  "RESERVED",
  "SOLD",
  "ARCHIVED",
];

type SearchParams = { [key: string]: string | string[] | undefined };

function parseVehicleStatus(value: string | undefined): VehicleStatus | undefined {
  if (!value) return undefined;
  return VEHICLE_STATUSES.includes(value as VehicleStatus) ? (value as VehicleStatus) : undefined;
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
  const status = parseVehicleStatus(typeof params.status === "string" ? params.status : undefined);

  const { vehicles, totalCount } = await listAdminVehicles({
    page,
    pageSize,
    status,
    search: q,
  });

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
        currentStatus={status}
        initialSearch={q ?? ""}
        canWrite={canWrite}
      />
    </div>
  );
}
