import { listPublicVehicles, getBrandsForFilter, getPublicPriceBounds } from "@/features/catalog/server/queries";
import { EmptyState } from "@/components/shared/EmptyState";
import { ScrollReveal } from "@/components/motion/ScrollReveal";
import { VehicleCard } from "@/features/catalog/ui/VehicleCard";
import { EstoqueToolbar } from "@/features/catalog/ui/EstoqueToolbar";
import type { FuelType, Transmission, VehicleType } from "@prisma/client";

export const metadata = {
  title: "Estoque de seminovos em Cascavel/PR",
  description:
    "Confira o estoque atual da FácilCar Multimarcas: seminovos selecionados para compra, troca e financiamento em Cascavel/PR.",
};

type SearchParams = { [key: string]: string | string[] | undefined };

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

  const [result, brands, priceBounds] = await Promise.all([
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
    getPublicPriceBounds(),
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
    <main className="min-h-screen px-4 py-5 sm:py-6">
      <div className="mx-auto max-w-6xl">
        <EstoqueToolbar
          brands={brands}
          priceBounds={priceBounds}
          resultCount={result.total}
          current={{
            q,
            brand,
            sort,
            type,
            fuelType,
            transmission,
            priceMin,
            priceMax,
            yearMin,
            yearMax,
          }}
        />

        {result.items.length === 0 ? (
          <div className="mt-8">
            <EmptyState
              title="Nenhum veículo encontrado"
              description="Ajuste os filtros ou entre em contato — podemos localizar o que você procura."
            />
          </div>
        ) : (
          <>
            <div className="mt-4 grid items-stretch gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {result.items.map((v, i) => (
                <ScrollReveal key={v.id} className="h-full" delay={(i % 3) * 60}>
                  <VehicleCard vehicle={v} headingLevel="h2" />
                </ScrollReveal>
              ))}
            </div>

            {result.totalPages > 1 && (
              <nav className="mt-10 flex justify-center gap-3">
                {page > 1 && (
                  <a
                    href={buildUrl({ page: page - 1 })}
                    className="rounded-lg border border-facil-border px-5 py-2 font-medium hover:bg-facil-surface"
                  >
                    Anterior
                  </a>
                )}
                <span className="flex items-center px-4 text-sm text-zinc-600 dark:text-zinc-400">
                  Página {page} de {result.totalPages}
                </span>
                {page < result.totalPages && (
                  <a
                    href={buildUrl({ page: page + 1 })}
                    className="rounded-lg border border-facil-border px-5 py-2 font-medium hover:bg-facil-surface"
                  >
                    Próxima
                  </a>
                )}
              </nav>
            )}
          </>
        )}
      </div>
    </main>
  );
}
