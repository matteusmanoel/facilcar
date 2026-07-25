import Link from "next/link";
import { listPublicVehicles, getBrandsForFilter } from "@/features/catalog/server/queries";
import { EmptyState } from "@/components/shared/EmptyState";
import { VehicleImage } from "@/components/shared/VehicleImage";
import { ScrollReveal } from "@/components/motion/ScrollReveal";
import { fuelLabels, transLabels } from "@/features/vehicle/lib/labels";
import type { FuelType, Transmission, VehicleType } from "@prisma/client";

type SearchParams = { [key: string]: string | string[] | undefined };

const TYPES: { value: VehicleType; label: string }[] = [
  { value: "CAR", label: "Carro" },
  { value: "UTILITY", label: "Picape / utilitário" },
  { value: "MOTORCYCLE", label: "Moto" },
  { value: "OTHER", label: "Outro" },
];

const FUELS: { value: FuelType; label: string }[] = [
  { value: "FLEX", label: "Flex" },
  { value: "GASOLINE", label: "Gasolina" },
  { value: "ETHANOL", label: "Etanol" },
  { value: "DIESEL", label: "Diesel" },
  { value: "ELECTRIC", label: "Elétrico" },
  { value: "HYBRID", label: "Híbrido" },
  { value: "OTHER", label: "Outro" },
];

const TRANS: { value: Transmission; label: string }[] = [
  { value: "MANUAL", label: "Manual" },
  { value: "AUTOMATIC", label: "Automático" },
  { value: "AUTOMATED", label: "Automatizado" },
  { value: "CVT", label: "CVT" },
  { value: "OTHER", label: "Outro" },
];

function num(v: string | undefined) {
  if (!v || v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export default async function EstoquePage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const page = Number(params.page) || 1;
  const q = typeof params.q === "string" ? params.q : undefined;
  const brand = typeof params.marca === "string" ? params.marca : undefined;
  const sort =
    typeof params.ordem === "string"
      ? (params.ordem as "priceAsc" | "priceDesc" | "yearDesc" | "newest" | "mileageAsc")
      : "newest";

  const type = typeof params.tipo === "string" && params.tipo ? (params.tipo as VehicleType) : undefined;
  const fuelType =
    typeof params.combustivel === "string" && params.combustivel
      ? (params.combustivel as FuelType)
      : undefined;
  const transmission =
    typeof params.cambio === "string" && params.cambio
      ? (params.cambio as Transmission)
      : undefined;
  const priceMin = num(typeof params.precoMin === "string" ? params.precoMin : undefined);
  const priceMax = num(typeof params.precoMax === "string" ? params.precoMax : undefined);
  const yearMin = num(typeof params.anoMin === "string" ? params.anoMin : undefined);
  const yearMax = num(typeof params.anoMax === "string" ? params.anoMax : undefined);

  const [result, brands] = await Promise.all([
    listPublicVehicles({
      q,
      brand,
      type,
      fuelType,
      transmission,
      priceMin,
      priceMax,
      yearMin,
      yearMax,
      sort,
      page,
    }),
    getBrandsForFilter(),
  ]);

  const buildUrl = (updates: Record<string, string | number | undefined>) => {
    const next = new URLSearchParams();
    const keys = [
      "q",
      "marca",
      "ordem",
      "tipo",
      "combustivel",
      "cambio",
      "precoMin",
      "precoMax",
      "anoMin",
      "anoMax",
    ] as const;
    for (const k of keys) {
      const v = params[k];
      if (typeof v === "string" && v) next.set(k, v);
    }
    Object.entries(updates).forEach(([k, v]) => {
      if (v !== undefined && v !== "") next.set(k, String(v));
      else next.delete(k);
    });
    const s = next.toString();
    return s ? `/estoque?${s}` : "/estoque";
  };

  return (
    <main className="min-h-screen py-10 px-4">
      <div className="mx-auto max-w-6xl">
        <div className="border-b border-facil-border pb-8">
          <h1 className="text-3xl font-extrabold text-foreground">Estoque</h1>
          <p className="mt-2 text-facil-muted">
            Filtre por marca, preço, ano e mais. Todas as informações são confirmadas na loja.
          </p>
        </div>

        <div className="mt-8 rounded-2xl border border-facil-border bg-facil-card p-6 shadow-sm">
          <form method="get" action="/estoque" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="block text-sm font-medium text-foreground sm:col-span-2">
              Busca
              <input
                type="search"
                name="q"
                defaultValue={q}
                placeholder="Modelo, marca..."
                className="public-form-input"
              />
            </label>
            <label className="block text-sm font-medium text-foreground">
              Marca
              <select
                name="marca"
                defaultValue={brand ?? ""}
                className="public-form-input"
              >
                <option value="">Todas</option>
                {brands.map((b) => (
                  <option key={b.id} value={b.slug}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium text-foreground">
              Tipo
              <select
                name="tipo"
                defaultValue={type ?? ""}
                className="public-form-input"
              >
                <option value="">Todos</option>
                {TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium text-foreground">
              Combustível
              <select
                name="combustivel"
                defaultValue={fuelType ?? ""}
                className="public-form-input"
              >
                <option value="">Todos</option>
                {FUELS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium text-foreground">
              Câmbio
              <select
                name="cambio"
                defaultValue={transmission ?? ""}
                className="public-form-input"
              >
                <option value="">Todos</option>
                {TRANS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium text-foreground">
              Preço mín. (R$)
              <input
                name="precoMin"
                type="number"
                defaultValue={priceMin ?? ""}
                className="public-form-input"
                placeholder="0"
              />
            </label>
            <label className="block text-sm font-medium text-foreground">
              Preço máx. (R$)
              <input
                name="precoMax"
                type="number"
                defaultValue={priceMax ?? ""}
                className="public-form-input"
                placeholder="300000"
              />
            </label>
            <label className="block text-sm font-medium text-foreground">
              Ano mín.
              <input
                name="anoMin"
                type="number"
                defaultValue={yearMin ?? ""}
                className="public-form-input"
                placeholder="2015"
              />
            </label>
            <label className="block text-sm font-medium text-foreground">
              Ano máx.
              <input
                name="anoMax"
                type="number"
                defaultValue={yearMax ?? ""}
                className="public-form-input"
                placeholder="2025"
              />
            </label>
            <label className="block text-sm font-medium text-foreground">
              Ordenar
              <select
                name="ordem"
                defaultValue={sort}
                className="public-form-input"
              >
                <option value="newest">Mais recentes</option>
                <option value="priceAsc">Menor preço</option>
                <option value="priceDesc">Maior preço</option>
                <option value="yearDesc">Ano mais novo</option>
                <option value="mileageAsc">Menor km</option>
              </select>
            </label>
            <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-4">
              <button
                type="submit"
                className="rounded-lg bg-facil-orange px-6 py-2.5 font-semibold text-white hover:bg-facil-orange-hover"
              >
                Filtrar
              </button>
              <Link
                href="/estoque"
                className="rounded-lg border border-facil-border px-6 py-2.5 font-medium text-foreground hover:bg-facil-surface"
              >
                Limpar
              </Link>
            </div>
          </form>
        </div>

        {result.items.length === 0 ? (
          <div className="mt-10">
            <EmptyState
              title="Nenhum veículo encontrado"
              description="Ajuste os filtros ou entre em contato — podemos localizar o que você procura."
            />
          </div>
        ) : (
          <>
            <p className="mt-8 text-sm font-medium text-facil-muted">
              {result.total} veículo(s) encontrado(s)
            </p>
            <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {result.items.map((v, i) => {
                const firstImage =
                  "images" in v && Array.isArray(v.images) ? v.images[0] : null;
                const fuel = v.fuelType
                  ? (fuelLabels[v.fuelType as FuelType] ?? v.fuelType)
                  : null;
                const trans = v.transmission
                  ? (transLabels[v.transmission as Transmission] ?? v.transmission)
                  : null;
                return (
                  <ScrollReveal key={v.id} delay={(i % 3) * 60}>
                    <Link
                      href={`/estoque/${v.slug}`}
                      className="vehicle-card group block"
                    >
                      <div className="relative aspect-[16/10] overflow-hidden bg-facil-surface">
                        <VehicleImage
                          src={firstImage?.url}
                          alt={v.title}
                          className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                        />
                        {v.yearModel && (
                          <span className="absolute right-3 top-3 badge-zinc">
                            {v.yearModel}
                          </span>
                        )}
                      </div>
                      <div className="p-5">
                        <h2 className="font-bold text-foreground line-clamp-2 transition-colors group-hover:text-facil-orange">
                          {v.title}
                        </h2>
                        <p className="mt-2 text-2xl font-black text-facil-orange">
                          {v.priceCash != null
                            ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                            : "Consultar"}
                        </p>
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {v.mileage != null && (
                            <span className="badge-zinc">
                              {v.mileage.toLocaleString("pt-BR")} km
                            </span>
                          )}
                          {fuel && <span className="badge-zinc">{fuel}</span>}
                          {trans && <span className="badge-zinc">{trans}</span>}
                        </div>
                      </div>
                    </Link>
                  </ScrollReveal>
                );
              })}
            </div>

            {result.totalPages > 1 && (
              <nav className="mt-12 flex justify-center gap-3">
                {page > 1 && (
                  <Link
                    href={buildUrl({ page: page - 1 })}
                    className="rounded-lg border border-facil-border px-5 py-2 font-medium hover:bg-facil-surface"
                  >
                    Anterior
                  </Link>
                )}
                <span className="flex items-center px-4 text-sm text-facil-muted">
                  Página {page} de {result.totalPages}
                </span>
                {page < result.totalPages && (
                  <Link
                    href={buildUrl({ page: page + 1 })}
                    className="rounded-lg border border-facil-border px-5 py-2 font-medium hover:bg-facil-surface"
                  >
                    Próxima
                  </Link>
                )}
              </nav>
            )}
          </>
        )}
      </div>
    </main>
  );
}
