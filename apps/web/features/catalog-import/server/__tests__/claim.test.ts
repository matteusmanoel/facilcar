import { beforeEach, describe, expect, it, vi } from "vitest";

const { updateMany, findFirst, findUnique, update } = vi.hoisted(() => ({
  updateMany: vi.fn(),
  findFirst: vi.fn(),
  findUnique: vi.fn(),
  update: vi.fn(),
}));

vi.mock("@/lib/db", () => ({
  prisma: {
    catalogImportItem: { updateMany, findFirst, findUnique, update },
  },
}));

import { claimReadyItem, claimItemById } from "../claim";

describe("claim atomicity", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("only one concurrent claim wins (updateMany count)", async () => {
    findFirst.mockResolvedValue({ id: "item-1" });
    updateMany.mockResolvedValueOnce({ count: 1 }).mockResolvedValueOnce({ count: 0 });

    const a = await claimReadyItem("worker-a");
    const b = await claimReadyItem("worker-b");
    expect(a).toBe("item-1");
    expect(b).toBeNull();
  });

  it("retry claim skips IMPORTED", async () => {
    findUnique.mockResolvedValue({ id: "item-1", status: "IMPORTED" });
    const ok = await claimItemById("item-1", "worker-a");
    expect(ok).toBe(false);
    expect(updateMany).not.toHaveBeenCalled();
  });

  it("retry unlocks FAILED then claims", async () => {
    findUnique.mockResolvedValue({ id: "item-1", status: "FAILED" });
    update.mockResolvedValue({});
    updateMany.mockResolvedValue({ count: 1 });
    const ok = await claimItemById("item-1", "worker-a");
    expect(ok).toBe(true);
    expect(update).toHaveBeenCalled();
    expect(updateMany).toHaveBeenCalled();
  });
});
