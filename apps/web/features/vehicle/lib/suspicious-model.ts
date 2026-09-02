/** Catalog/import domain — UI/placeholder tokens that must never become Vehicle.model. */

export const SUSPICIOUS_MODEL_TOKENS = [
  "view",
  "click",
  "edit",
  "null",
  "undefined",
  "none",
  "n/a",
  "na",
  "test",
  "string",
  "não informado",
  "nao informado",
] as const;

export function normalizeModelToken(value: string | null | undefined): string {
  if (!value) return "";
  return value
    .normalize("NFKC")
    .replace(/[\u0000-\u001F\u007F-\u009F\u200B-\u200F\u202A-\u202E\u2060\uFEFF]/g, "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

export function isSuspiciousVehicleModel(model: string | null | undefined): boolean {
  const token = normalizeModelToken(model);
  if (!token) return true;
  if ((SUSPICIOUS_MODEL_TOKENS as readonly string[]).includes(token)) return true;
  return false;
}
