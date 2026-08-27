import { createHash } from "node:crypto";

const REDACT = "[REDACTED_MEDIA]";
const MAX_JSON_CHARS = 200_000;
const SENSITIVE_KEY =
  /^(base64|data|filebase64|mediakey|mediakeyiv|fileencsha256|filesha256|jpegthumbnail|token|apikey|authorization|secret|password)$/i;

function walk(value: unknown, depth = 0): unknown {
  if (depth > 12) return "[TRUNCATED_DEPTH]";
  if (Array.isArray(value)) return value.map((v) => walk(v, depth + 1));
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (SENSITIVE_KEY.test(k)) {
        out[k] = REDACT;
        continue;
      }
      if (typeof v === "string" && v.length > 500 && /^[A-Za-z0-9+/=]+$/.test(v.slice(0, 80))) {
        out[k] = REDACT;
        continue;
      }
      out[k] = walk(v, depth + 1);
    }
    return out;
  }
  return value;
}

export function sanitizePayload(payload: unknown): {
  sanitized: unknown;
  truncated: boolean;
  payloadHash: string;
} {
  const sanitized = walk(payload);
  let json = JSON.stringify(sanitized);
  let truncated = false;
  if (json.length > MAX_JSON_CHARS) {
    json = json.slice(0, MAX_JSON_CHARS) + "…[TRUNCATED]";
    truncated = true;
  }
  const payloadHash = createHash("sha256").update(json).digest("hex");
  let parsed: unknown = sanitized;
  if (truncated) {
    try {
      parsed = JSON.parse(json.replace(/…\[TRUNCATED\]$/, ""));
    } catch {
      parsed = { truncated: true, preview: json.slice(0, 2000) };
    }
  }
  return { sanitized: parsed, truncated, payloadHash };
}
