import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getVehicleBySlug, getRelatedVehicles } from "@/features/vehicle/server/queries";
import { getSiteSettings } from "@/features/settings/server/queries";
import { VehicleInterestForm } from "@/features/lead/ui/VehicleInterestForm";
import { VehicleGallery } from "@/features/vehicle/ui/VehicleGallery";
import { VehicleDetailAccordion } from "@/features/vehicle/ui/VehicleDetailAccordion";
import { VehicleImage } from "@/components/shared/VehicleImage";
import { BRAND } from "@/lib/brand";
import { fuelLabels, transLabels } from "@/features/vehicle/lib/labels";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const vehicle = await getVehicleBySlug(slug);
  if (!vehicle) return { title: "Veículo" };
  const title = vehicle.metaTitle ?? vehicle.title;
  const description =
    vehicle.metaDescription ?? vehicle.shortDescription ?? vehicle.description?.slice(0, 160) ?? undefined;
  return {
    title,
    description,
    openGraph: {
      title,
      description,
    },
  };
}

export default async function VehicleDetailPage({ params }: Props) {
  const { slug } = await params;
  const vehicle = await getVehicleBySlug(slug);
  if (!vehicle) notFound();

  const [settings, related] = await Promise.all([
    getSiteSettings(),
    getRelatedVehicles(vehicle.id, 6),
  ]);

  const whatsappNumber = settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";
  const whatsappUrl = whatsappNumber
    ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(`Olá! Tenho interesse no veículo: ${vehicle.title}`)}`
    : "#";

  const sortedImages = [...vehicle.images].sort((a, b) => a.sortOrder - b.sortOrder);
  const siteName = settings?.siteName ?? BRAND.name;

  const subtitle =
    vehicle.shortDescription?.trim() ||
    [vehicle.model, vehicle.version].filter(Boolean).join(" ").trim() ||
    null;

  const quickStats: string[] = [];
  if (vehicle.mileage != null) {
    quickStats.push(`${vehicle.mileage.toLocaleString("pt-BR")} km`);
  }
  if (vehicle.transmission) {
    const t = vehicle.transmission;
    quickStats.push(transLabels[t] ?? t);
  }
  if (vehicle.fuelType) {
    const f = vehicle.fuelType;
    quickStats.push(fuelLabels[f] ?? f);
  }
  if (vehicle.city || vehicle.state) {
    quickStats.push([vehicle.city, vehicle.state].filter(Boolean).join(" / "));
  }

  return (
    <main className="min-h-screen py-6 px-4 md:py-10">
      <div className="mx-auto max-w-7xl">
        <Link
          href="/estoque"
          className="text-sm font-medium text-facil-orange hover:underline"
        >
          ← Voltar ao estoque
        </Link>

        <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_min(100%,400px)] lg:items-start lg:gap-10">
          {/* Coluna principal: título + galeria + accordion (desktop) */}
          <header className="min-w-0 lg:col-start-1 lg:row-start-1">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-bold text-green-800">
                Revisado / conferido
              </span>
              <span className="rounded-full bg-facil-orange/15 px-3 py-1 text-xs font-bold text-facil-orange">
                Documentação em dia
              </span>
            </div>
            <h1 className="mt-3 text-2xl font-extrabold uppercase tracking-tight text-zinc-900 md:text-3xl lg:text-[1.75rem] lg:leading-tight">
              {vehicle.title}
            </h1>
            {subtitle && (
              <p className="mt-2 text-base font-medium text-zinc-600 md:text-lg">{subtitle}</p>
            )}
            <p className="mt-4 text-3xl font-black tracking-tight text-facil-orange md:text-4xl">
              {vehicle.priceCash != null
                ? `R$ ${Number(vehicle.priceCash).toLocaleString("pt-BR")}`
                : "Consultar valor"}
            </p>
            {(vehicle.pricePromotional || vehicle.priceTradeIn) && (
              <p className="mt-2 text-sm text-facil-muted">
                {vehicle.pricePromotional != null &&
                  `Promoção: R$ ${Number(vehicle.pricePromotional).toLocaleString("pt-BR")} · `}
                {vehicle.priceTradeIn != null &&
                  `Troca a partir de R$ ${Number(vehicle.priceTradeIn).toLocaleString("pt-BR")}`}
              </p>
            )}
            {quickStats.length > 0 && (
              <p className="mt-4 flex flex-wrap gap-x-2 gap-y-1 text-sm text-facil-muted">
                {quickStats.map((s, i) => (
                  <span key={s} className="inline-flex items-center gap-2">
                    {i > 0 && <span className="text-zinc-300" aria-hidden>·</span>}
                    <span>{s}</span>
                  </span>
                ))}
              </p>
            )}
          </header>

          <div className="min-w-0 lg:col-start-1 lg:row-start-2">
            <VehicleGallery images={sortedImages} title={vehicle.title} />
          </div>

          {/* Sidebar: formulário (mobile após galeria; desktop coluna 2) */}
          <aside className="lg:col-start-2 lg:row-start-1 lg:row-span-3 lg:sticky lg:top-24 lg:self-start">
            <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-lg shadow-zinc-900/5">
              <h2 className="text-xl font-bold text-zinc-900">Envie seu interesse</h2>
              <p className="mt-2 text-sm leading-relaxed text-facil-muted">
                Preencha seus dados — retornamos com mais informações e agendamento de visita ou test drive.
              </p>
              <div className="mt-5">
                <VehicleInterestForm vehicleId={vehicle.id} />
              </div>
              <div className="mt-6 space-y-3 border-t border-zinc-100 pt-6">
                {whatsappNumber && (
                  <a
                    href={whatsappUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-facil-primary flex w-full justify-center py-3 text-base font-bold"
                  >
                    WhatsApp
                  </a>
                )}
                <Link
                  href="/financiamento"
                  className="btn-facil-outline flex w-full justify-center py-3 text-base font-bold"
                >
                  Financiar este veículo
                </Link>
              </div>
            </div>
          </aside>

          <div className="min-w-0 lg:col-start-1 lg:row-start-3">
            <VehicleDetailAccordion vehicle={vehicle} siteName={siteName} />
          </div>
        </div>

        {related.length > 0 && (
          <section className="mt-16 border-t border-zinc-200 pt-12">
            <h2 className="text-2xl font-bold text-zinc-900">Veículos relacionados</h2>
            <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {related.map((v) => (
                <Link
                  key={v.id}
                  href={`/estoque/${v.slug}`}
                  className="group overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm hover:border-facil-orange/30"
                >
                  <div className="aspect-video overflow-hidden bg-zinc-100">
                    <VehicleImage
                      src={v.images[0]?.url}
                      alt={v.title}
                      className="h-full w-full object-cover group-hover:scale-105"
                    />
                  </div>
                  <div className="p-4">
                    <h3 className="font-semibold text-zinc-900">{v.title}</h3>
                    <p className="mt-1 font-bold text-facil-orange">
                      {v.priceCash != null
                        ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                        : "Consultar"}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
