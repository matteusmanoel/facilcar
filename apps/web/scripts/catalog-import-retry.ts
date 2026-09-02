import { config } from "dotenv";
import { resolve } from "node:path";

config({ path: resolve(process.cwd(), ".env") });
config({ path: resolve(process.cwd(), ".env.local"), override: true });

async function main() {
  const itemId = process.argv[2];
  if (!itemId) {
    console.error("Usage: catalog-import:retry -- <itemId>");
    process.exit(1);
  }
  const { retryItem } = await import("../features/catalog-import/server/worker");
  await retryItem(itemId);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
