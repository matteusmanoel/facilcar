export type PublicVehiclePrice = {
  current: number | null;
  original: number | null;
  compare: boolean;
};

export function toPublicMoney(value: unknown): number | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function formatPublicPrice(value: number): string {
  return `R$ ${value.toLocaleString("pt-BR")}`;
}

/** Public offer: strike the announced cash price when a lower pass-through exists. */
export function publicVehiclePrice(input: {
  priceCash?: unknown;
  priceRetailAsIs?: unknown;
}): PublicVehiclePrice {
  const original = toPublicMoney(input.priceCash);
  const repasse = toPublicMoney(input.priceRetailAsIs);

  if (original != null && repasse != null && repasse < original) {
    return { current: repasse, original, compare: true };
  }
  if (original != null) return { current: original, original: null, compare: false };
  if (repasse != null) return { current: repasse, original: null, compare: false };
  return { current: null, original: null, compare: false };
}
