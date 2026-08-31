import Link from "next/link";
import { Plus } from "lucide-react";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { canWriteVehicles } from "@/features/auth/rbac-config";
import { getBrandsForFilter } from "@/features/catalog/server/queries";
import { parseAdminVehicleListParams } from "@/features/vehicle/lib/admin-vehicle-filters";
import { getAdminVehicleNumericBounds, listAdminVehicles } from "@/features/vehicle/server/queries";
import { Button } from "@/components/ui/button";
import { VehiclesClient } from "./VehiclesClient";

type SearchParams = { [key: string]: string | string[] | undefined };

export default async function AdminVeiculosPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const user = await guardAdminSection("veiculos");
  const canWrite = canWriteVehicles(user.role);
  const parsed = parseAdminVehicleListParams(await searchParams);

  const [{ vehicles, totalCount }, brands, numericBounds] = await Promise.all([
    listAdminVehicles({
      page: parsed.page,
      pageSize: parsed.pageSize,
      statuses: parsed.statuses,
      search: parsed.search,
      brandIds: parsed.brandIds,
      types: parsed.types,
      featuredValues: parsed.featuredValues,
      fuelTypes: parsed.fuelTypes,
      transmissions: parsed.transmissions,
      stockTypes: parsed.stockTypes,
      commercialHistories: parsed.commercialHistories,
      hasPhotoValues: parsed.hasPhotoValues,
      priceMin: parsed.priceMin,
      priceMax: parsed.priceMax,
      yearMin: parsed.yearMin,
      yearMax: parsed.yearMax,
    }),
    getBrandsForFilter(),
    getAdminVehicleNumericBounds(),
  ]);

  const serializedVehicles = vehicles.map((vehicle) => ({
    id: vehicle.id,
    slug: vehicle.slug,
    title: vehicle.title,
    status: vehicle.status,
    stockType: vehicle.stockType,
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
        page={parsed.page}
        pageSize={parsed.pageSize}
        brands={brands}
        filters={{
          statuses: parsed.statuses,
          brandIds: parsed.brandIds,
          types: parsed.types,
          featuredValues: parsed.featuredValues,
          fuelTypes: parsed.fuelTypes,
          transmissions: parsed.transmissions,
          stockTypes: parsed.stockTypes,
          commercialHistories: parsed.commercialHistories,
          hasPhotoValues: parsed.hasPhotoValues,
          priceMin: parsed.priceMin,
          priceMax: parsed.priceMax,
          yearMin: parsed.yearMin,
          yearMax: parsed.yearMax,
        }}
        initialSearch={parsed.search ?? ""}
        canWrite={canWrite}
        priceBounds={numericBounds.price}
        yearBounds={numericBounds.year}
      />
    </div>
  );
}
