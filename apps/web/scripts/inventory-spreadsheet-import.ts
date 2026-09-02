import { config } from "dotenv";
import { resolve } from "node:path";
import { readFile } from "node:fs/promises";

config({ path: resolve(process.cwd(), ".env") });
config({ path: resolve(process.cwd(), ".env.local"), override: true });

function repoRoot(): string {
  const cwd = process.cwd();
  return cwd.endsWith("/apps/web") ? resolve(cwd, "../..") : cwd;
}

function parseArgs(argv: string[]) {
  const confirmedMatches: Record<string, string> = {};
  for (const arg of argv) {
    if (!arg.startsWith("--match=")) continue;
    const rest = arg.slice("--match=".length);
    const eq = rest.indexOf("=");
    if (eq <= 0) throw new Error(`--match inválido: ${arg}`);
    confirmedMatches[rest.slice(0, eq)] = rest.slice(eq + 1);
  }
  return {
    apply: argv.includes("--apply"),
    skipDraftAbsent: argv.includes("--skip-draft-absent"),
    file: argv.find((arg) => arg.startsWith("--file="))?.slice("--file=".length),
    confirmedMatches,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const { prisma } = await import("../lib/db");
  const {
    applyReconcilePlan,
    buildPlan,
    loadDbVehiclesForReconcile,
    persistImportRun,
    summarizePlan,
  } = await import("../features/vehicle/server/inventory-import");
  type InventorySnapshotFile = import("../features/vehicle/server/inventory-import").InventorySnapshotFile;

  try {
    const snapshotPath = args.file
      ? resolve(args.file)
      : resolve(repoRoot(), "estoque.json");
    const raw = JSON.parse(await readFile(snapshotPath, "utf8")) as InventorySnapshotFile;
    const snapshots = raw.vehicles;
    if (!Array.isArray(snapshots) || snapshots.length === 0) {
      throw new Error("estoque.json não contém veículos");
    }

    const dbVehicles = await loadDbVehiclesForReconcile();
    const plan = buildPlan(snapshots, dbVehicles, { confirmedMatches: args.confirmedMatches });
    if (args.skipDraftAbsent) {
      plan.rows = plan.rows.filter((row) => row.action !== "DRAFT_ABSENT");
    }
    const summary = summarizePlan(plan);

    const publicRow = (row: (typeof plan.rows)[number]) => ({
      spreadsheetKey: row.spreadsheetKey,
      plate: row.plateNormalized,
      action: row.action,
      confidence: row.confidence,
      vehicleId: row.vehicleId,
      candidateIds: row.candidateIds,
      notes: row.notes,
      title: row.snapshot.rawDescription,
      stockType: row.snapshot.stockType,
      patches: row.patches.filter((patch) => !patch.preservedBecauseNull),
      preserved: row.patches.filter((patch) => patch.preservedBecauseNull).map((patch) => patch.field),
      owners: row.ownerNames,
    });

    const report = {
      sourceFile: raw.dataset?.sourceFile ?? snapshotPath,
      schemaVersion: raw.schemaVersion ?? null,
      snapshotCount: snapshots.length,
      dbCount: dbVehicles.length,
      dryRun: !args.apply,
      summary,
      byAction: {
        UPDATE: plan.rows.filter((row) => row.action === "UPDATE").map(publicRow),
        CREATE: plan.rows.filter((row) => row.action === "CREATE").map(publicRow),
        CONFLICT: plan.rows.filter((row) => row.action === "CONFLICT").map(publicRow),
        DRAFT_ABSENT: plan.rows.filter((row) => row.action === "DRAFT_ABSENT").map(publicRow),
      },
      preservedBecauseNull: summary.preserved,
    };

    if (!args.apply) {
      const persisted = await persistImportRun({
        sourceFile: String(report.sourceFile),
        schemaVersion: raw.schemaVersion,
        dryRun: true,
        applied: false,
        plan,
      });
      console.log(JSON.stringify({ ...report, runId: persisted.runId }, null, 2));
      return;
    }

    const applied = await applyReconcilePlan(plan);
    const persisted = await persistImportRun({
      sourceFile: String(report.sourceFile),
      schemaVersion: raw.schemaVersion,
      dryRun: false,
      applied: true,
      plan,
      appliedIds: applied.appliedIds,
    });
    console.log(
      JSON.stringify(
        {
          ...report,
          dryRun: false,
          runId: persisted.runId,
          applied: {
            inserted: applied.inserted,
            updated: applied.updated,
            drafted: applied.drafted,
            skippedConflicts: applied.skippedConflicts,
          },
        },
        null,
        2,
      ),
    );
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
