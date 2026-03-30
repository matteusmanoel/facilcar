import { headers } from "next/headers";

const WINDOW_MS = 60_000; // 1 minute
const MAX_REQUESTS = 5;

const store = new Map<string, { count: number; resetAt: number }>();

function getKey(identifier: string): string {
  return `lead:${identifier}`;
}

export async function checkRateLimit(identifier?: string): Promise<{
  ok: boolean;
  error?: string;
}> {
  let id = identifier;
  if (!id) {
    try {
      const hdrs = await headers();
      id =
        hdrs.get("x-forwarded-for")?.split(",")[0]?.trim() ??
        hdrs.get("x-real-ip") ??
        "anonymous";
    } catch {
      id = "anonymous";
    }
  }

  const key = getKey(id);
  const now = Date.now();
  const entry = store.get(key);

  if (!entry || entry.resetAt < now) {
    store.set(key, { count: 1, resetAt: now + WINDOW_MS });
    return { ok: true };
  }

  if (entry.count >= MAX_REQUESTS) {
    return {
      ok: false,
      error: "Muitas tentativas. Aguarde 1 minuto e tente novamente.",
    };
  }

  entry.count += 1;
  return { ok: true };
}
