/** Normalizes phone to digits-only for storage and lookup. */
export function normalizePhone(phone: string): string {
  return phone.replace(/\D/g, "");
}
