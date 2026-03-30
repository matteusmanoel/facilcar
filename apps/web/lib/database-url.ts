/**
 * URL e SSL compartilhados entre `lib/db.ts`, `prisma/seed.ts` e qualquer script que use `pg` + Prisma adapter.
 */

export function isProbablyLocalDatabase(url: string): boolean {
  return (
    url.includes("127.0.0.1") ||
    url.includes("localhost") ||
    url.includes("host.docker.internal")
  );
}

/**
 * Em pg 8.13+, `sslmode=require` pode equivaler a verify-full; hosts gerenciados (Supabase, etc.)
 * podem falhar com erro de certificado. O aviso do `pg` recomenda `uselibpqcompat=true`.
 */
export function normalizeDatabaseUrl(url: string): string {
  if (!url || isProbablyLocalDatabase(url)) return url;
  try {
    const parsed = new URL(url);
    if (!parsed.searchParams.has("uselibpqcompat")) {
      parsed.searchParams.set("uselibpqcompat", "true");
    }
    return parsed.toString();
  } catch {
    return url;
  }
}

/** Opções extra do `pg` Pool para URLs remotas (alinhado a `lib/db.ts`). */
export function getPgPoolSslExtras(connectionString: string): { ssl?: { rejectUnauthorized: boolean } } {
  const sslEnv = process.env.DATABASE_SSL_REJECT_UNAUTHORIZED?.toLowerCase();
  const sslRelaxed = sslEnv === "false" || sslEnv === "0" || sslEnv === "no";
  if (!isProbablyLocalDatabase(connectionString) && sslRelaxed) {
    return { ssl: { rejectUnauthorized: false } };
  }
  return {};
}
