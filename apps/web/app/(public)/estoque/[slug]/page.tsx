import Link from "next/link";
import { notFound } from "next/navigation";
import { getVehicleBySlug, getRelatedVehicles } from "@/features/vehicle/server/queries";
import { getSiteSettings } from "@/features/settings/server/queries";
import { VehicleInterestForm } from "@/features/lead/ui/VehicleInterestForm";

export default async function VehicleDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const vehicle = await getVehicleBySlug(slug);
  if (!vehicle) notFound();

  const [settings, related] = await Promise.all([
    getSiteSettings(),
    getRelatedVehicles(vehicle.id, 6),
  ]);

  const whatsappNumber = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";
  const whatsappUrl = whatsappNumber
    ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(`Olá, tenho interesse no veículo: ${vehicle.title}`)}`
    : "#";

  return (
    <main className="min-h-screen py-8 px-4">
      <div className="mx-auto max-w-6xl">
        <Link href="/estoque" className="text-sm text-zinc-600 hover:underline">
          ← Voltar ao estoque
        </Link>

        <div className="mt-6 grid gap-8 lg:grid-cols-2">
          <div className="space-y-2">
            {vehicle.images.length > 0 ? (
              <div className="aspect-video overflow-hidden rounded-lg bg-zinc-200">
                <img
                  src={vehicle.images[0]?.url ?? ""}
                  alt={vehicle.title}
                  className="h-full w-full object-cover"
                />
              </div>
            ) : (
              <div className="aspect-video rounded-lg bg-zinc-200" />
            )}
            {vehicle.images.length > 1 && (
              <div className="flex gap-2 overflow-x-auto">
                {vehicle.images.slice(1, 5).map((img) => (
                  <div key={img.id} className="h-20 w-28 flex-shrink-0 overflow-hidden rounded">
                    <img src={img.url} alt="" className="h-full w-full object-cover" />
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <h1 className="text-2xl font-semibold">{vehicle.title}</h1>
            <p className="mt-2 text-2xl font-bold">
              {vehicle.priceCash != null
                ? `R$ ${Number(vehicle.priceCash).toLocaleString("pt-BR")}`
                : "Consultar valor"}
            </p>

            <div className="mt-6 grid grid-cols-2 gap-2 text-sm">
              <span className="text-zinc-500">Marca</span>
              <span>{vehicle.brand.name}</span>
              <span className="text-zinc-500">Ano/Modelo</span>
              <span>{vehicle.yearModel ?? vehicle.yearManufacture ?? "—"}</span>
              <span className="text-zinc-500">Câmbio</span>
              <span>{vehicle.transmission ?? "—"}</span>
              <span className="text-zinc-500">Combustível</span>
              <span>{vehicle.fuelType ?? "—"}</span>
              <span className="text-zinc-500">Cor</span>
              <span>{vehicle.color ?? "—"}</span>
              <span className="text-zinc-500">Quilometragem</span>
              <span>{vehicle.mileage != null ? `${vehicle.mileage.toLocaleString("pt-BR")} km` : "—"}</span>
            </div>

            {vehicle.features.length > 0 && (
              <div className="mt-6">
                <h3 className="font-medium">Opcionais</h3>
                <ul className="mt-2 flex flex-wrap gap-2">
                  {vehicle.features.map((f) => (
                    <li key={f.id} className="rounded bg-zinc-100 px-2 py-1 text-sm">
                      {f.label}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {vehicle.description && (
              <div className="mt-6">
                <h3 className="font-medium">Descrição</h3>
                <p className="mt-2 text-zinc-600 whitespace-pre-wrap">{vehicle.description}</p>
              </div>
            )}

            <div className="mt-8 flex gap-4">
              {whatsappNumber && (
                <a
                  href={whatsappUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg bg-green-600 px-6 py-3 font-medium text-white hover:bg-green-700"
                >
                  WhatsApp
                </a>
              )}
              <Link
                href="/financiamento"
                className="rounded-lg border border-zinc-300 px-6 py-3 font-medium hover:bg-zinc-50"
              >
                Financiar este veículo
              </Link>
            </div>

            <div className="mt-10 border-t pt-8">
              <h3 className="font-medium">Tenho interesse neste veículo</h3>
              <div className="mt-4 max-w-sm">
                <VehicleInterestForm vehicleId={vehicle.id} />
              </div>
            </div>
          </div>
        </div>

        {related.length > 0 && (
          <section className="mt-12">
            <h2 className="text-xl font-semibold">Veículos relacionados</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {related.map((v) => (
                <Link
                  key={v.id}
                  href={`/estoque/${v.slug}`}
                  className="rounded-lg border bg-white p-4 shadow-sm hover:shadow"
                >
                  <div className="aspect-video bg-zinc-200 rounded mb-2">
                    {v.images[0] && (
                      <img src={v.images[0].url} alt="" className="h-full w-full object-cover rounded" />
                    )}
                  </div>
                  <h3 className="font-medium">{v.title}</h3>
                  <p className="text-sm text-zinc-600">
                    {v.priceCash != null
                      ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                      : "Consultar valor"}
                  </p>
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
