import path from "path";
import fs from "fs";
import dotenv from "dotenv";
import { defineConfig } from "prisma/config";

// Segue a hierarquia do Next.js: .env.local > .env
// Isso permite usar Docker local (.env.local) e Supabase prod (.env) sem conflito.
const root = path.resolve(process.cwd());
const envLocal = path.join(root, ".env.local");
const envFile = path.join(root, ".env");

if (fs.existsSync(envLocal)) {
  dotenv.config({ path: envLocal, override: true });
} else if (fs.existsSync(envFile)) {
  dotenv.config({ path: envFile });
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
