import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getVehicleBySlug,
  getRelatedVehicles,
  type VehicleWithBrandAndPreviewImages,
} from "@/features/vehicle/server/queries";
import { getSiteSettings } from "@/features/settings/server/queries";
import { FinancingSimulationForm } from "@/features/lead/ui/FinancingSimulationForm";
import { VehicleGallery } from "@/features/vehicle/ui/VehicleGallery";
import { VehicleDetailAccordion } from "@/features/vehicle/ui/VehicleDetailAccordion";
import { VehicleImage } from "@/components/shared/VehicleImage";
import { BRAND } from "@/lib/brand";
import { fuelLabels, transLabels } from "@/features/vehicle/lib/labels";
import { buildCarJsonLd } from "@/lib/seo";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const vehicle = await getVehicleBySlug(slug);
  if (!vehicle) return { title: "Veículo" };

  const title = vehicle.metaTitle ?? vehicle.title;
  const description =
    vehicle.metaDescription ??
    vehicle.shortDescription ??
    vehicle.description?.slice(0, 160) ??
    undefined;

  const sortedImages = [...vehicle.images].sort((a, b) => a.sortOrder - b.sortOrder);
  const coverImage = sortedImages[0]?.url;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      ...(coverImage
        ? { images: [{ url: coverImage, width: 1200, height: 630, alt: title }] }
        : {}),
    },
  };
}

export default async function VehicleDetailPage({ params }: Props) {
  const { slug } = await params;
  const vehicle = await getVehicleBySlug(slug);
  if (!vehicle) notFound();

  const [settings, related]: [
    Awaited<ReturnType<typeof getSiteSettings>>,
    VehicleWithBrandAndPreviewImages[],
  ] = await Promise.all([getSiteSettings(), getRelatedVehicles(vehicle.id, 6)]);

  const whatsappNumber =
    settings?.defaultWhatsappNumber?.replace(/\D/g, "") ?? "";
  const whatsappUrl = whatsappNumber
    ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(`Olá! Tenho interesse no veículo: ${vehicle.title}`)}`
    : "#";

  const sortedImages = [...vehicle.images].sort(
    (a, b) => a.sortOrder - b.sortOrder,
  );
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

  const estimatedMonthly =
    vehicle.priceCash != null
      ? Math.round(Number(vehicle.priceCash) / 60).toLocaleString("pt-BR")
      : null;

  const carJsonLd = buildCarJsonLd({
    title: vehicle.title,
    slug: vehicle.slug,
    description: vehicle.description,
    shortDescription: vehicle.shortDescription,
    priceCash: vehicle.priceCash,
    yearModel: vehicle.yearModel,
    mileage: vehicle.mileage,
    color: vehicle.color,
    fuelType: vehicle.fuelType ?? undefined,
    brand: vehicle.brand,
    images: sortedImages,
  });

  return (
    <main className="min-h-screen py-6 px-4 md:py-10">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(carJsonLd) }}
      />
      <div className="mx-auto max-w-7xl">
        <Link
          href="/estoque"
          className="text-sm font-medium text-facil-orange hover:underline"
        >
          ← Voltar ao estoque
        </Link>

        <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_min(100%,400px)] lg:items-start lg:gap-10">
          {/* Coluna principal: título + galeria + accordion */}
          <header className="min-w-0 lg:col-start-1 lg:row-start-1">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-bold text-green-800">
                Revisado / conferido
              </span>
              <span className="rounded-full bg-facil-orange/15 px-3 py-1 text-xs font-bold text-facil-orange">
                Documentação em dia
              </span>
              <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-bold text-blue-700">
                Financiamento facilitado
              </span>
            </div>
            <h1 className="mt-3 text-2xl font-extrabold uppercase tracking-tight text-zinc-900 md:text-3xl lg:text-[1.75rem] lg:leading-tight">
              {vehicle.title}
            </h1>
            {subtitle && (
              <p className="mt-2 text-base font-medium text-zinc-600 md:text-lg">
                {subtitle}
              </p>
            )}
            <p className="mt-4 text-3xl font-black tracking-tight text-facil-orange md:text-4xl">
              {vehicle.priceCash != null
                ? `R$ ${Number(vehicle.priceCash).toLocaleString("pt-BR")}`
                : "Consultar valor"}
            </p>
            {estimatedMonthly && (
              <p className="mt-1 text-sm text-zinc-500">
                ou financie a partir de{" "}
                <strong className="text-zinc-700">~R$ {estimatedMonthly}/mês*</strong>
              </p>
            )}
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
                    {i > 0 && (
                      <span className="text-zinc-300" aria-hidden>
                        ·
                      </span>
                    )}
                    <span>{s}</span>
                  </span>
                ))}
              </p>
            )}
          </header>

          <div className="min-w-0 lg:col-start-1 lg:row-start-2">
            <VehicleGallery images={sortedImages} title={vehicle.title} />
          </div>

          {/* Sidebar: simulação de financiamento */}
          <aside className="lg:col-start-2 lg:row-start-1 lg:row-span-3 lg:sticky lg:top-24 lg:self-start">
            <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-lg shadow-zinc-900/5">
              <h2 className="text-xl font-bold text-zinc-900">
                Simule seu Financiamento
              </h2>
              <p className="mt-1.5 text-sm leading-relaxed text-facil-muted">
                Preencha seus dados em segundos e receba a análise de crédito pelo
                WhatsApp. 100% gratuito, sem compromisso.
              </p>
              <div className="mt-5">
                <FinancingSimulationForm
                  vehicleId={vehicle.id}
                  vehicleTitle={vehicle.title}
                  vehicleYear={vehicle.yearModel ?? undefined}
                  vehicleModel={vehicle.model}
                  whatsappNumber={settings?.defaultWhatsappNumber ?? ""}
                />
              </div>
              {whatsappNumber && (
                <div className="mt-4 border-t border-zinc-100 pt-4">
                  <p className="mb-2 text-center text-xs text-zinc-400">
                    Prefere falar direto?
                  </p>
                  <a
                    href={whatsappUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-facil-outline flex w-full items-center justify-center gap-2 py-2.5 text-sm font-semibold"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                      aria-hidden
                    >
                      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                    </svg>
                    Chamar no WhatsApp
                  </a>
                </div>
              )}
            </div>
            <p className="mt-2 px-1 text-center text-xs text-zinc-400">
              *Sujeito à análise de crédito. Valor estimado em 60 meses sem entrada.
            </p>
          </aside>

          <div className="min-w-0 lg:col-start-1 lg:row-start-3">
            <VehicleDetailAccordion vehicle={vehicle} siteName={siteName} />
          </div>
        </div>

        {related.length > 0 && (
          <section className="mt-16 border-t border-zinc-200 pt-12">
            <h2 className="text-2xl font-bold text-zinc-900">
              Veículos relacionados
            </h2>
            <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {related.map((v: VehicleWithBrandAndPreviewImages) => (
                <Link
                  key={v.id}
                  href={`/estoque/${v.slug}`}
                  className="group overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm hover:border-facil-orange/30"
                >
                  <div className="relative aspect-video overflow-hidden bg-zinc-100">
                    <VehicleImage
                      src={v.images[0]?.url}
                      alt={v.title}
                      className="h-full w-full object-cover transition group-hover:scale-105"
                    />
                  </div>
                  <div className="p-4">
                    <h3 className="font-semibold text-zinc-900">{v.title}</h3>
                    <p className="mt-1 font-bold text-facil-orange">
                      {v.priceCash != null
                        ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                        : "Consultar"}
                    </p>
                    <p className="mt-2 text-xs text-zinc-500">Simule o financiamento →</p>
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
