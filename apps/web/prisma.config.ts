import path from "path";
import fs from "fs";
import dotenv from "dotenv";
import { defineConfig } from "prisma/config";

// Hierarquia tipo Next.js: .env, depois .env.local (sobrescreve chaves do .env).
// Variáveis já definidas no ambiente (ex.: `DATABASE_URL=... npx prisma migrate deploy`)
// NUNCA são sobrescritas — antes, `override: true` em .env.local anulava o valor do shell.
const root = path.resolve(process.cwd());
const envLocal = path.join(root, ".env.local");
const envFile = path.join(root, ".env");

const shellSnapshot: NodeJS.ProcessEnv = { ...process.env };

if (fs.existsSync(envFile)) {
  dotenv.config({ path: envFile, override: true });
}
if (fs.existsSync(envLocal)) {
  dotenv.config({ path: envLocal, override: true });
}

for (const key of Object.keys(shellSnapshot)) {
  const v = shellSnapshot[key];
  if (v !== undefined) {
    process.env[key] = v;
  }
}

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: {
    path: "prisma/migrations",
  },
  datasource: {
    url: process.env["DATABASE_URL"],
  },
});
