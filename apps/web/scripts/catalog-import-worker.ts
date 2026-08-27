import { config } from "dotenv";
import { resolve } from "node:path";

config({ path: resolve(process.cwd(), ".env") });
config({ path: resolve(process.cwd(), ".env.local"), override: true });

async function main() {
  const { runWorkerLoop } = await import("../features/catalog-import/server/worker");
  const once = process.argv.includes("--once");
  await runWorkerLoop({ once });
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
