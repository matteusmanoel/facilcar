/** Empty input means “clear this field”, not 0. */
export function parseOptionalNumber(raw: string | number | null | undefined): number | null {
  if (raw == null) return null;
  const text = String(raw).trim().replace(",", ".");
  if (!text) return null;
  const n = Number(text);
  return Number.isFinite(n) ? n : Number.NaN;
}

export function parseOptionalInt(
  raw: string | number | null | undefined,
  opts?: { min?: number; max?: number },
): number | null {
  const n = parseOptionalNumber(raw);
  if (n == null) return null;
  if (!Number.isInteger(n)) return Number.NaN;
  if (opts?.min != null && n < opts.min) return Number.NaN;
  if (opts?.max != null && n > opts.max) return Number.NaN;
  return n;
}

export function isInvalidNumber(n: number | null): boolean {
  return n != null && Number.isNaN(n);
}

export function toDateInputValue(value: Date | string | null | undefined): string {
  if (!value) return "";
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function parseDateInputValue(iso: string | null | undefined): Date | null {
  const trimmed = iso?.trim() ?? "";
  if (!trimmed) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return null;
  const parsed = new Date(`${trimmed}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function maskCPF(cpf: string | null | undefined): string {
  if (!cpf) return "—";
  const digits = cpf.replace(/\D/g, "");
  if (digits.length !== 11) return cpf;
  return `***.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
}
