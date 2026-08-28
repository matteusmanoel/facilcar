import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { guardVehicleWrite } from "@/features/auth/server/rbac";
import { getBrandsForVehicleForm } from "@/features/catalog/server/queries";
import { VehicleForm } from "../VehicleForm";

export default async function AdminVeiculoNovoPage() {
  await guardVehicleWrite();
  const brands = await getBrandsForVehicleForm();

  return (
    <div className="admin-page flex flex-col gap-4">
      <div>
        <Link
          href="/admin/veiculos"
          className="inline-flex items-center gap-1 text-sm text-zinc-600 hover:text-zinc-950 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Voltar para veículos
        </Link>
        <h1 className="mt-2 admin-page-title">Novo veículo</h1>
        <p className="admin-page-subtitle">
          Preencha as informações em cada etapa
        </p>
      </div>

      <VehicleForm brands={brands} canManageBrands />
    </div>
  );
}
