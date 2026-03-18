import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { getBrandsForFilter } from "@/features/catalog/server/queries";
import { VehicleForm } from "../VehicleForm";

export default async function AdminVeiculoEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [vehicle, brands] = await Promise.all([
    prisma.vehicle.findUnique({
      where: { id },
      include: { images: { orderBy: { sortOrder: "asc" } }, features: { orderBy: { sortOrder: "asc" } } },
    }),
    getBrandsForFilter(),
  ]);

  if (!vehicle) notFound();

  return (
    <main className="p-6">
      <Link href="/admin/veiculos" className="text-sm text-zinc-600 hover:underline">
        ← Voltar
      </Link>
      <h1 className="mt-4 text-2xl font-semibold">Editar: {vehicle.title}</h1>
      <VehicleForm brands={brands} vehicle={vehicle} />
    </main>
  );
}
