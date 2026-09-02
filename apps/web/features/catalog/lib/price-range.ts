export type PriceBounds = { min: number; max: number };

function orderedBounds(bounds: PriceBounds): { lo: number; hi: number } {
  return {
    lo: Math.min(bounds.min, bounds.max),
    hi: Math.max(bounds.min, bounds.max),
  };
}

export function clampPrice(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

export function priceSliderStep(min: number, max: number): number {
  const span = Math.max(max - min, 0);
  if (span <= 0) return 1;
  if (span <= 20_000) return 100;
  if (span <= 80_000) return 500;
  return 1_000;
}

export function sliderValuesFromFilters(
  bounds: PriceBounds,
  priceMin?: number,
  priceMax?: number,
): [number, number] {
  const { lo, hi } = orderedBounds(bounds);
  const start =
    priceMin != null && Number.isFinite(priceMin) ? clampPrice(priceMin, lo, hi) : lo;
  const end =
    priceMax != null && Number.isFinite(priceMax) ? clampPrice(priceMax, lo, hi) : hi;
  return start <= end ? [start, end] : [end, start];
}

/** Empty string means “no filter” (thumb parked at that bound). */
export function filtersFromSliderValues(
  bounds: PriceBounds,
  values: [number, number],
): { min: string; max: string } {
  const { lo, hi } = orderedBounds(bounds);
  const start = Math.min(values[0], values[1]);
  const end = Math.max(values[0], values[1]);
  return {
    min: start <= lo ? "" : String(start),
    max: end >= hi ? "" : String(end),
  };
}

export function parsePriceInput(raw: string): number | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return undefined;
  const n = Number(trimmed);
  return Number.isFinite(n) ? n : undefined;
}

export function formatCatalogPrice(n: number): string {
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
}
