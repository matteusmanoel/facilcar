import {
  listPublicVehicles,
  getBrandsForFilter,
  getPublicPriceBounds,
  getPublicYearBounds,
} from "@/features/catalog/server/queries";
import { EmptyState } from "@/components/shared/EmptyState";
import { EstoqueToolbar } from "@/features/catalog/ui/EstoqueToolbar";
import { EstoqueFeed } from "@/features/catalog/ui/EstoqueFeed";
import { parseBodyStyleParam, hasActiveCatalogFilters } from "@/features/catalog/lib/public-catalog";
import { catalogFullBleedClass } from "@/features/catalog/lib/shell";
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
  const q = typeof params.q === "string" ? params.q : undefined;
  const brand = typeof params.marca === "string" ? params.marca : undefined;
  const sort =
    typeof params.ordem === "string"
      ? (params.ordem as "priceAsc" | "priceDesc" | "yearDesc" | "newest" | "mileageAsc")
      : "newest";

  const type = typeof params.tipo === "string" && params.tipo ? (params.tipo as VehicleType) : undefined;
  const bodyStyle = parseBodyStyleParam(
    typeof params.carroceria === "string" ? params.carroceria : undefined,
  );
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

  const filters = {
    q,
    brand,
    type,
    bodyStyle,
    fuelType,
    transmission,
    priceMin,
    priceMax,
    yearMin,
    yearMax,
    sort,
    page: 1,
  };

  const [result, brands, priceBounds, yearBounds] = await Promise.all([
    listPublicVehicles(filters),
    getBrandsForFilter(),
    getPublicPriceBounds(),
    getPublicYearBounds(),
  ]);

  const filtered = hasActiveCatalogFilters(filters);

  return (
    <main className="min-h-screen py-5 sm:py-6">
      <div className={catalogFullBleedClass}>
        <EstoqueToolbar
          brands={brands}
          priceBounds={priceBounds}
          yearBounds={yearBounds}
          resultCount={result.total}
          current={{
            q,
            brand,
            sort,
            type,
            bodyStyle,
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
              showClearFilters
            />
          </div>
        ) : (
          <EstoqueFeed
            initialItems={result.items}
            total={result.total}
            filters={filters}
            showClearFilters={filtered}
          />
        )}
      </div>
    </main>
  );
}
