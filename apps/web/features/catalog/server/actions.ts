"use server";

import { listPublicVehicles, type CatalogFilters } from "@/features/catalog/server/queries";

export async function loadMorePublicVehicles(filters: CatalogFilters, page: number) {
  return listPublicVehicles({ ...filters, page });
}
