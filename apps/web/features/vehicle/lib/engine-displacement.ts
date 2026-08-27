/** Commercial engine displacement in liters (1.0, 1.4, 1.8, 2.0). */

export const ENGINE_DISPLACEMENT_MIN = 0.6;
export const ENGINE_DISPLACEMENT_MAX = 8.0;

const TOKEN = /\b([1-8][.,][0-9])\b/g;

export type EngineParseResult = {
  liters: number | null;
  warning?: string;
};

function hasOneDecimal(n: number): boolean {
  return Math.abs(n * 10 - Math.round(n * 10)) < 1e-8;
}

export function normalizeEngineDisplacementLiters(raw: unknown): number | null {
  if (raw === null || raw === undefined || raw === "") return null;
  if (typeof raw === "boolean") return null;
  if (typeof raw === "number") {
    if (!Number.isFinite(raw) || !hasOneDecimal(raw)) return null;
    if (raw < ENGINE_DISPLACEMENT_MIN || raw > ENGINE_DISPLACEMENT_MAX) return null;
    return Math.round(raw * 10) / 10;
  }
  const text = String(raw).trim().replace(",", ".");
  if (!text) return null;
  if (/[a-zA-Z]/.test(text)) return null;
  if ((text.match(/\./g) ?? []).length !== 1) return null;
  const n = Number(text);
  if (!Number.isFinite(n) || !hasOneDecimal(n)) return null;
  if (n < ENGINE_DISPLACEMENT_MIN || n > ENGINE_DISPLACEMENT_MAX) return null;
  return Math.round(n * 10) / 10;
}

export function parseEngineDisplacementFromAdText(text: string): EngineParseResult {
  const matches = [...text.matchAll(TOKEN)].map((m) =>
    normalizeEngineDisplacementLiters(m[1]!.replace(",", ".")),
  );
  const unique = [...new Set(matches.filter((v): v is number => v != null))];
  if (unique.length === 0) return { liters: null };
  if (unique.length > 1) return { liters: null, warning: "ENGINE_AMBIGUOUS" };
  const rest = text.replace(TOKEN, " ").replace(/\s+/g, " ").trim();
  if (/[a-zA-Z]/.test(rest) && /\b(tsi|turbo|fire|flex|16v)\b/i.test(text)) {
    return { liters: unique[0]!, warning: "ENGINE_QUALIFIER_UNSPLIT" };
  }
  return { liters: unique[0]! };
}
