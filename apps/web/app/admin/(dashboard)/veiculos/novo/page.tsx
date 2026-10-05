import { guardVehicleWrite } from "@/features/auth/server/rbac";
import { getBrandsForVehicleForm, getPartnersForVehicleForm } from "@/features/catalog/server/queries";
import { VehicleForm } from "../VehicleForm";

export default async function AdminVeiculoNovoPage() {
  await guardVehicleWrite();
  const [brands, partners] = await Promise.all([getBrandsForVehicleForm(), getPartnersForVehicleForm()]);

  return (
    <div className="mx-auto flex h-[calc(100dvh-8.5rem)] w-full max-w-7xl flex-col overflow-hidden px-4 py-3 sm:px-6 md:h-dvh lg:px-8">
      <VehicleForm brands={brands} partners={partners} canManageBrands />
    </div>
  );
}
