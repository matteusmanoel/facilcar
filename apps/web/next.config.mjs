import path from "path";
import { fileURLToPath } from "url";

/**
 * Diretório do app Next (`apps/web`): é onde estão `package.json`, `node_modules` e o PostCSS
 * que resolve `@import "tailwindcss"`. Se `turbopack.root` for a raiz do monorepo, o bundler
 * tenta resolver `tailwindcss` a partir de `apps/` ou do repo — pastas sem dependências — e falha.
 */
const appRoot = path.dirname(fileURLToPath(import.meta.url));
const tailwindcssPkg = path.resolve(appRoot, "node_modules/tailwindcss");

/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    root: appRoot,
    // Garante resolução de `@import "tailwindcss"` mesmo quando o contexto de resolve
    // cai em `apps/` (sem node_modules) em layouts tipo apps/web.
    resolveAlias: {
      tailwindcss: tailwindcssPkg,
    },
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "picsum.photos", pathname: "/**" },
      { protocol: "https", hostname: "fastly.picsum.photos", pathname: "/**" },
    ],
  },
};

export default nextConfig;
