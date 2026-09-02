export type VehicleStockTypeValue = "OWNED" | "CONSIGNED";

export type SnapshotPricing = {
  fipe?: number | null;
  cashPrice?: number | null;
  retailWithWarranty?: number | null;
  retailAsIs?: number | null;
  ownerAsking?: number | null;
};

/** Public/SDR announced price. Internal fields stay off the catalog contract. */
export function announcedPriceFromSnapshot(
  stockType: VehicleStockTypeValue,
  pricing: SnapshotPricing,
): number | null {
  if (stockType === "OWNED") {
    return pricing.cashPrice ?? null;
  }
  return pricing.retailWithWarranty ?? null;
}
