import Link from "next/link";
import { listPublicVehicles, getBrandsForFilter } from "@/features/catalog/server/queries";
import { EmptyState } from "@/components/shared/EmptyState";

type SearchParams = { [key: string]: string | string[] | undefined };

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
      ? (params.ordem as "priceAsc" | "priceDesc" | "yearDesc" | "newest")
      : "newest";

  const [result, brands] = await Promise.all([
    listPublicVehicles({
      q,
      brand,
      sort,
      page,
    }),
    getBrandsForFilter(),
  ]);

  const buildUrl = (updates: Record<string, string | number | undefined>) => {
    const next = new URLSearchParams();
    if (params.q) next.set("q", String(params.q));
    if (params.marca) next.set("marca", String(params.marca));
    if (params.ordem) next.set("ordem", String(params.ordem));
    Object.entries(updates).forEach(([k, v]) => {
      if (v !== undefined && v !== "") next.set(k, String(v));
    });
    return `/estoque?${next.toString()}`;
  };

  return (
    <main className="min-h-screen py-8 px-4">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-2xl font-semibold">Estoque</h1>

        <div className="mt-6 flex flex-wrap gap-4">
          <form method="get" action="/estoque" className="flex flex-wrap gap-2">
            <input
              type="search"
              name="q"
              defaultValue={q}
              placeholder="Buscar"
              className="rounded border border-zinc-300 px-3 py-2"
            />
            <select
              name="marca"
              defaultValue={brand ?? ""}
              className="rounded border border-zinc-300 px-3 py-2"
            >
              <option value="">Todas as marcas</option>
              {brands.map((b) => (
                <option key={b.id} value={b.slug}>
                  {b.name}
                </option>
              ))}
            </select>
            <select
              name="ordem"
              defaultValue={sort}
              className="rounded border border-zinc-300 px-3 py-2"
            >
              <option value="newest">Mais recentes</option>
              <option value="priceAsc">Preço: menor</option>
              <option value="priceDesc">Preço: maior</option>
              <option value="yearDesc">Ano: mais novo</option>
            </select>
            <button type="submit" className="rounded bg-zinc-900 px-4 py-2 text-white hover:bg-zinc-800">
              Filtrar
            </button>
          </form>
        </div>

        {result.items.length === 0 ? (
          <EmptyState
            title="Nenhum veículo encontrado"
            description="Tente ajustar os filtros ou volte mais tarde."
          />
        ) : (
          <>
            <p className="mt-4 text-sm text-zinc-600">
              {result.total} veículo(s) encontrado(s)
            </p>
            <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {result.items.map((v) => {
                const firstImage = "images" in v && Array.isArray(v.images) ? v.images[0] : null;
                return (
                <Link
                  key={v.id}
                  href={`/estoque/${v.slug}`}
                  className="rounded-lg border bg-white shadow-sm transition hover:shadow"
                >
                  <div className="aspect-video bg-zinc-200 rounded-t-lg">
                    {firstImage && (
                      <img
                        src={firstImage.url}
                        alt=""
                        className="h-full w-full object-cover rounded-t-lg"
                      />
                    )}
                  </div>
                  <div className="p-4">
                    <h2 className="font-semibold">{v.title}</h2>
                    <p className="mt-1 text-sm text-zinc-600">
                      {v.priceCash != null
                        ? `R$ ${Number(v.priceCash).toLocaleString("pt-BR")}`
                        : "Consultar valor"}
                    </p>
                    <p className="mt-1 text-xs text-zinc-500">
                      {v.yearModel} · {v.mileage != null ? `${v.mileage.toLocaleString("pt-BR")} km` : "—"} · {v.fuelType ?? "—"}
                    </p>
                  </div>
                </Link>
              );})}
            </div>

            {result.totalPages > 1 && (
              <nav className="mt-8 flex justify-center gap-2">
                {page > 1 && (
                  <Link
                    href={buildUrl({ page: page - 1 })}
                    className="rounded border px-4 py-2 hover:bg-zinc-100"
                  >
                    Anterior
                  </Link>
                )}
                <span className="flex items-center px-4">
                  Página {page} de {result.totalPages}
                </span>
                {page < result.totalPages && (
                  <Link
                    href={buildUrl({ page: page + 1 })}
                    className="rounded border px-4 py-2 hover:bg-zinc-100"
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
