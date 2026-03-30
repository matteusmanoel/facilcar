import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
import { Pool } from "pg";

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

function isProbablyLocalDatabase(url: string): boolean {
  return (
    url.includes("127.0.0.1") ||
    url.includes("localhost") ||
    url.includes("host.docker.internal")
  );
}

/**
 * Em pg 8.13+, `sslmode=require` na URL passa a equivaler a verify-full; em hosts
 * gerenciados (Supabase, Neon, etc.) isso pode gerar na Vercel:
 * "self-signed certificate in certificate chain" (Prisma P1011) durante o build.
 * O próprio aviso do `pg` recomenda `uselibpqcompat=true&sslmode=require` para o
 * comportamento anterior de TLS com `require`.
 */
function normalizeDatabaseUrl(url: string): string {
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

function createPrismaClient() {
  const raw = process.env.DATABASE_URL;
  if (!raw) {
    if (process.env.NODE_ENV === "production") {
      throw new Error("DATABASE_URL is required in production (ex.: Supabase Postgres).");
    }
  }

  const connectionString = normalizeDatabaseUrl(
    raw ?? "postgresql://postgres:postgres@127.0.0.1:5432/facilcar",
  );

  const sslEnv = process.env.DATABASE_SSL_REJECT_UNAUTHORIZED?.toLowerCase();
  const sslRelaxed = sslEnv === "false" || sslEnv === "0" || sslEnv === "no";

  const pool = new Pool({
    connectionString,
    ...(!isProbablyLocalDatabase(connectionString) && sslRelaxed
      ? { ssl: { rejectUnauthorized: false } }
      : {}),
  });

  const adapter = new PrismaPg(pool);
  return new PrismaClient({
    adapter,
    log: process.env.NODE_ENV === "development" ? ["error", "warn"] : ["error"],
  });
}

export const prisma = globalForPrisma.prisma ?? createPrismaClient();

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
