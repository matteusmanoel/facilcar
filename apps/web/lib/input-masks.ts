/** Digit-only slice, optionally capped. */
export function digitsOnly(value: string, max?: number): string {
  const digits = value.replace(/\D/g, "");
  return max != null ? digits.slice(0, max) : digits;
}

/** National BR number as the user types: (00) 00000-0000 */
function formatNationalPhoneBR(d: string): string {
  if (d.length === 0) return "";
  if (d.length <= 2) return `(${d}`;
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  if (d.length <= 10) {
    return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  }
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7, 11)}`;
}

/**
 * Brazilian phone as the user types.
 * National numbers cap at 11 digits. Stored WhatsApp/SDR values with country
 * code 55 (12–13 digits) keep every digit so edit+save cannot truncate the key.
 */
export function formatPhoneBR(value: string): string {
  const raw = digitsOnly(value);
  if (raw.startsWith("55") && raw.length > 11) {
    const d = raw.slice(0, 13);
    const national = formatNationalPhoneBR(d.slice(2));
    return national ? `+55 ${national}` : "+55";
  }
  return formatNationalPhoneBR(digitsOnly(value, 11));
}

export function formatCPF(value: string): string {
  const d = digitsOnly(value, 11);
  return d
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/(\d{3})\.(\d{3})\.(\d{3})(\d)/, "$1.$2.$3-$4");
}

export function formatCNPJ(value: string): string {
  const d = digitsOnly(value, 14);
  return d
    .replace(/(\d{2})(\d)/, "$1.$2")
    .replace(/(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/(\d{2})\.(\d{3})\.(\d{3})(\d)/, "$1.$2.$3/$4")
    .replace(/(\d{2})\.(\d{3})\.(\d{3})\/(\d{4})(\d)/, "$1.$2.$3/$4-$5");
}

/** Display a numeric amount as 1.234,56. Empty when value is missing. */
export function formatBRL(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return "";
  return Number(value).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Parse a typed/masked BRL string; last two digits are cents. */
export function parseBRL(formatted: string): number | undefined {
  const digits = digitsOnly(formatted);
  if (!digits) return undefined;
  return Number(digits) / 100;
}
