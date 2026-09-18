import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["features/**/*.test.ts", "features/**/__tests__/**/*.ts"],
    env: {
      SDR_ENVIRONMENT: "sandbox",
      SDR_OUTBOUND_POLICY: "allowlist",
      SDR_OUTBOUND_ALLOWLIST: "5545988432998,5511999000101,5545999000000",
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
