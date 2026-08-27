import { beforeEach, describe, expect, it, vi } from "vitest";

const prisma = vi.hoisted(() => ({
  catalogImportItem: {
    findUnique: vi.fn(),
    update: vi.fn(),
    findFirst: vi.fn(),
    updateMany: vi.fn(),
  },
  catalogImportEvent: {
    findMany: vi.fn(),
    update: vi.fn(),
    updateMany: vi.fn(),
  },
  catalogMediaAsset: {
    findMany: vi.fn(),
    upsert: vi.fn(),
  },
  $transaction: vi.fn(async (arg: unknown) => {
    if (typeof arg === "function") return arg(prisma);
    if (Array.isArray(arg)) return Promise.all(arg);
    return arg;
  }),
  brand: { findFirst: vi.fn(), create: vi.fn(), findUnique: vi.fn() },
  vehicle: { create: vi.fn() },
}));

vi.mock("@/lib/db", () => ({ prisma }));

vi.mock("../openai-extract", () => ({
  openaiExtractVehicle: vi.fn(),
}));

vi.mock("../evolution-media", () => ({
  processItemMedia: vi.fn(async () => ({ warnings: [] })),
}));

describe("retry / create-draft idempotency", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("createDraftFromImport no-ops when vehicleId already set", async () => {
    const { createDraftFromImport } = await import("../create-draft");
    prisma.catalogImportItem.findUnique.mockResolvedValue({
      id: "item-1",
      vehicleId: "veh-existing",
      warnings: [],
      events: [],
      mediaAssets: [],
    });
    prisma.catalogImportItem.update.mockResolvedValue({});
    prisma.catalogImportEvent.updateMany.mockResolvedValue({ count: 1 });

    const result = await createDraftFromImport("item-1");
    expect(result.status).toBe("IMPORTED");
    expect(result.vehicleId).toBe("veh-existing");
    expect(prisma.vehicle.create).not.toHaveBeenCalled();
  });

  it("retryItem no-ops when already IMPORTED", async () => {
    const { retryItem } = await import("../worker");
    prisma.catalogImportItem.findUnique.mockResolvedValue({
      id: "item-1",
      status: "IMPORTED",
      vehicleId: "veh-1",
    });
    await retryItem("item-1");
    expect(prisma.catalogImportItem.updateMany).not.toHaveBeenCalled();
  });
});
