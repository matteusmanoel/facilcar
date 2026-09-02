import type { NextRequest } from "next/server";

export function assertCatalogImportSecret(req: NextRequest): boolean {
  const expected = process.env.CATALOG_IMPORT_SECRET;
  if (!expected) return false;
  const header =
    req.headers.get("authorization")?.replace(/^Bearer\s+/i, "").trim() ||
    req.headers.get("x-catalog-import-secret")?.trim() ||
    "";
  return header.length > 0 && header === expected;
}
