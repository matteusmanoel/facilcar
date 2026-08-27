/** Parse comma-separated query param into trimmed tokens. */
export function parseCsvParam(value: string | undefined): string[] {
  if (!value?.trim()) return [];
  return value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

/** Serialize tokens to CSV or undefined when empty. */
export function serializeCsvParam(values: string[]): string | undefined {
  const unique = [...new Set(values.filter(Boolean))];
  return unique.length ? unique.join(",") : undefined;
}

/** Parse CSV into enum values, ignoring unknown tokens. */
export function parseEnumCsv<T extends string>(
  value: string | undefined,
  allowed: readonly T[],
): T[] {
  const set = new Set(allowed);
  return parseCsvParam(value).filter((v): v is T => set.has(v as T));
}
