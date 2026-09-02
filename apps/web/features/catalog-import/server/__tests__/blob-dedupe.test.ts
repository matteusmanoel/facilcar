import { beforeEach, describe, expect, it, vi } from "vitest";
import { createHash } from "node:crypto";

const prisma = vi.hoisted(() => ({
  catalogMediaAsset: {
    findMany: vi.fn(),
    update: vi.fn(),
  },
  catalogMediaBlob: {
    findUnique: vi.fn(),
    create: vi.fn(),
  },
  catalogImportEvent: {
    findUnique: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock("@/lib/db", () => ({ prisma }));

vi.mock("@/features/storage/server/s3-client", () => ({
  isVehicleStorageConfigured: () => true,
}));

const uploadVehicleImageBuffer = vi.fn();
vi.mock("@/features/storage/server/upload-vehicle-image", () => ({
  uploadVehicleImageBuffer,
}));

vi.mock("../evolution-media", async (importOriginal) => {
  // re-import after mocks — we test processItemMedia by stubbing download via fetch
  return importOriginal();
});

describe("blob dedupe", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          base64: Buffer.from("same-bytes").toString("base64"),
          mimetype: "image/jpeg",
        }),
      })),
    );
    process.env.EVOLUTION_API_URL = "http://localhost:8081";
    process.env.EVOLUTION_API_KEY = "key";
    process.env.EVOLUTION_INSTANCE = "facilcar";
  });

  it("reuses CatalogMediaBlob by sha256 for N assets", async () => {
    const { processItemMedia } = await import("../evolution-media");
    const sha = createHash("sha256").update(Buffer.from("same-bytes")).digest("hex");

    prisma.catalogMediaAsset.findMany.mockResolvedValue([
      { id: "a1", eventId: "e1", status: "PENDING", sortOrder: 1 },
      { id: "a2", eventId: "e2", status: "PENDING", sortOrder: 2 },
    ]);
    prisma.catalogImportEvent.findUnique
      .mockResolvedValueOnce({ id: "e1", mediaRef: { type: "imageMessage", message: {} } })
      .mockResolvedValueOnce({ id: "e2", mediaRef: { type: "imageMessage", message: {} } });

    prisma.catalogMediaBlob.findUnique
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({ id: "blob-1", sha256: sha });

    uploadVehicleImageBuffer.mockResolvedValue({
      key: "vehicles/x.jpg",
      publicUrl: "https://cdn/x.jpg",
    });
    prisma.catalogMediaBlob.create.mockResolvedValue({ id: "blob-1", sha256: sha });
    prisma.catalogMediaAsset.update.mockResolvedValue({});
    prisma.catalogImportEvent.update.mockResolvedValue({});

    await processItemMedia("item-1");

    expect(uploadVehicleImageBuffer).toHaveBeenCalledTimes(1);
    const statuses = prisma.catalogMediaAsset.update.mock.calls.map((c) => {
      const arg = c[0] as { data: { status: string } };
      return arg.data.status;
    });
    expect(statuses).toContain("UPLOADED");
    expect(statuses).toContain("SKIPPED_DEDUPED");
  });
});
