import path from "path";
import { fileURLToPath } from "url";

/** Diretório deste arquivo = `apps/web`. */
const appRoot = path.dirname(fileURLToPath(import.meta.url));
/** Raiz do repositório (pai de `apps/`). Igual ao `outputFileTracingRoot` no Vercel em monorepo. */
const workspaceRoot = path.resolve(appRoot, "..", "..");

/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    root: workspaceRoot,
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "picsum.photos", pathname: "/**" },
      { protocol: "https", hostname: "fastly.picsum.photos", pathname: "/**" },
    ],
  },
};

export default nextConfig;
