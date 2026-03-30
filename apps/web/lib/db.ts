import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
import { Pool } from "pg";
import { getPgPoolSslExtras, normalizeDatabaseUrl } from "@/lib/database-url";

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

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

  const pool = new Pool({
    connectionString,
    ...getPgPoolSslExtras(connectionString),
  });

  const adapter = new PrismaPg(pool);
  return new PrismaClient({
    adapter,
    log: process.env.NODE_ENV === "development" ? ["error", "warn"] : ["error"],
  });
}

export const prisma = globalForPrisma.prisma ?? createPrismaClient();

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
