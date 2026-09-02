const PLATE_BODY = /^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$/;

export function normalizePlate(raw: string | null | undefined): string | null {
  if (raw == null) return null;
  const compact = String(raw)
    .normalize("NFKC")
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, "");
  if (!compact) return null;
  if (!PLATE_BODY.test(compact)) return null;
  return compact;
}

export function formatPlate(normalized: string | null | undefined): string | null {
  if (!normalized || normalized.length !== 7) return normalized ?? null;
  return `${normalized.slice(0, 3)}-${normalized.slice(3)}`;
}

export function plateFinalFromPlate(normalized: string | null | undefined): string | null {
  if (!normalized) return null;
  return normalized.slice(-1);
}
