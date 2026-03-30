import path from "path";
import { fileURLToPath } from "url";

/**
 * Diretório do app Next (`apps/web`): é onde estão `package.json`, `node_modules` e o PostCSS
 * que resolve `@import "tailwindcss"`. Se `turbopack.root` for a raiz do monorepo, o bundler
 * tenta resolver `tailwindcss` a partir de `apps/` ou do repo — pastas sem dependências — e falha.
 */
const appRoot = path.dirname(fileURLToPath(import.meta.url));
const tailwindcssPkg = path.resolve(appRoot, "node_modules/tailwindcss");

const supabaseImageHost = process.env.NEXT_PUBLIC_SUPABASE_HOST;

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Mesmo valor que `turbopack.root` (evita aviso e divergência no trace na Vercel).
  outputFileTracingRoot: appRoot,
  turbopack: {
    root: appRoot,
    // Garante resolução de `@import "tailwindcss"` mesmo quando o contexto de resolve
    // cai em `apps/` (sem node_modules) em layouts tipo apps/web.
    resolveAlias: {
      tailwindcss: tailwindcssPkg,
    },
  },
  images: {
    formats: ["image/avif", "image/webp"],
    remotePatterns: [
      { protocol: "https", hostname: "picsum.photos", pathname: "/**" },
      { protocol: "https", hostname: "fastly.picsum.photos", pathname: "/**" },
      ...(supabaseImageHost
        ? [
            {
              protocol: "https",
              hostname: supabaseImageHost,
              pathname: "/storage/v1/object/public/**",
            },
          ]
        : []),
      ...(process.env.NEXT_PUBLIC_R2_PUBLIC_HOST
        ? [
            {
              protocol: "https",
              hostname: process.env.NEXT_PUBLIC_R2_PUBLIC_HOST,
              pathname: "/**",
            },
          ]
        : []),
    ],
  },
};

export default nextConfig;
