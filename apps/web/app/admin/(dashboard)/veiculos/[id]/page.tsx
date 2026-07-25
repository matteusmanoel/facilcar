import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft, ExternalLink } from "lucide-react";
import { prisma } from "@/lib/db";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { canWriteVehicles } from "@/features/auth/rbac-config";
import { getBrandsForFilter } from "@/features/catalog/server/queries";
import { VehicleForm } from "../VehicleForm";
import { ArchiveVehicleButton } from "../ArchiveVehicleButton";

export default async function AdminVeiculoEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await guardAdminSection("veiculos");
  const readOnly = !canWriteVehicles(user.role);
  const { id } = await params;
  const [vehicle, brands] = await Promise.all([
    prisma.vehicle.findUnique({
      where: { id },
      include: {
        images: { orderBy: { sortOrder: "asc" } },
        features: { orderBy: { sortOrder: "asc" } },
      },
    }),
    getBrandsForFilter(),
  ]);

  if (!vehicle) notFound();

  const serializedVehicle = {
    ...vehicle,
    priceCash: vehicle.priceCash != null ? Number(vehicle.priceCash) : null,
    priceTradeIn: vehicle.priceTradeIn != null ? Number(vehicle.priceTradeIn) : null,
    pricePromotional: vehicle.pricePromotional != null ? Number(vehicle.pricePromotional) : null,
    parcelaBase: vehicle.parcelaBase != null ? Number(vehicle.parcelaBase) : null,
    entradaMinima: vehicle.entradaMinima != null ? Number(vehicle.entradaMinima) : null,
    rendaMinimaSugerida: vehicle.rendaMinimaSugerida != null ? Number(vehicle.rendaMinimaSugerida) : null,
  };

  return (
    <div className="admin-page flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <Link
            href="/admin/veiculos"
            className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Voltar para veículos
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-zinc-900 dark:text-zinc-50">
            {readOnly ? "Veículo:" : "Editar:"} {vehicle.title}
          </h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            Atualizado em{" "}
            {new Date(vehicle.updatedAt).toLocaleDateString("pt-BR", {
              day: "2-digit",
              month: "long",
              year: "numeric",
            })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!readOnly && (
            <ArchiveVehicleButton
              vehicleId={vehicle.id}
              vehicleTitle={vehicle.title}
              currentStatus={vehicle.status}
              variant="edit"
            />
          )}
          <Link
            href={`/estoque/${vehicle.slug}`}
            target="_blank"
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Ver no site
          </Link>
        </div>
      </div>

      <VehicleForm brands={brands} vehicle={serializedVehicle} readOnly={readOnly} />
    </div>
  );
}
