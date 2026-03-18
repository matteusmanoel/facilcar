import Link from "next/link";
import { getBrandsForFilter } from "@/features/catalog/server/queries";
import { VehicleForm } from "../VehicleForm";

export default async function AdminVeiculoNovoPage() {
  const brands = await getBrandsForFilter();

  return (
    <main className="p-6">
      <Link href="/admin/veiculos" className="text-sm text-zinc-600 hover:underline">
        ← Voltar
      </Link>
      <h1 className="mt-4 text-2xl font-semibold">Novo veículo</h1>
      <VehicleForm brands={brands} />
    </main>
  );
}
