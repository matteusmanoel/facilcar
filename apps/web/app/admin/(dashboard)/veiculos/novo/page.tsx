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
          className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          Voltar para veículos
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-zinc-900 dark:text-zinc-50">Novo veículo</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
          Preencha as informações em cada etapa
        </p>
      </div>

      <VehicleForm brands={brands} canManageBrands />
    </div>
  );
}
