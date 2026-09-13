"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { VehicleCard, type VehicleCardVehicle } from "@/features/catalog/ui/VehicleCard";
import { loadMorePublicVehicles } from "@/features/catalog/server/actions";
import type { CatalogFilters } from "@/features/catalog/lib/public-catalog";
import { catalogCardGridClass } from "@/features/catalog/lib/shell";
import { ClearFiltersButton } from "@/features/catalog/ui/ClearFiltersButton";

type Props = {
  initialItems: VehicleCardVehicle[];
  total: number;
  filters: CatalogFilters;
  showClearFilters?: boolean;
};

export function EstoqueFeed({ initialItems, total, filters, showClearFilters = false }: Props) {
  const [items, setItems] = useState(initialItems);
  const [page, setPage] = useState(1);
  const [isPending, startTransition] = useTransition();
  const sentinelRef = useRef<HTMLDivElement>(null);
  const hasMore = items.length < total;

  useEffect(() => {
    setItems(initialItems);
    setPage(1);
  }, [initialItems]);

  function loadNext() {
    if (!hasMore || isPending) return;
    const nextPage = page + 1;
    startTransition(async () => {
      const result = await loadMorePublicVehicles(filters, nextPage);
      setItems((prev) => {
        const seen = new Set(prev.map((item) => item.id));
        return [...prev, ...result.items.filter((item) => !seen.has(item.id))];
      });
      setPage(nextPage);
    });
  }

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || !hasMore) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) loadNext();
      },
      { rootMargin: "400px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasMore, isPending, page, filters]);

  return (
    <>
      <div className={`mt-4 ${catalogCardGridClass}`}>
        {items.map((vehicle) => (
          <VehicleCard key={vehicle.id} vehicle={vehicle} headingLevel="h2" />
        ))}
      </div>
      {hasMore ? (
        <div ref={sentinelRef} className="mt-8 flex justify-center">
          <button
            type="button"
            onClick={loadNext}
            disabled={isPending}
            className="w-full rounded-lg border border-facil-border px-5 py-3 font-medium hover:bg-facil-surface sm:w-auto"
          >
            {isPending ? "Carregando…" : "Carregar mais"}
          </button>
        </div>
      ) : null}
      {showClearFilters ? (
        <div className="mt-8 flex justify-center">
          <ClearFiltersButton />
        </div>
      ) : null}
    </>
  );
}
