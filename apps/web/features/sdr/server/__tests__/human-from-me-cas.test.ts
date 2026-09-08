import { describe, expect, it } from "vitest";
import { humanFromMeOwnershipCas } from "../human-from-me-cas";

describe("humanFromMeOwnershipCas", () => {
  const lastAt = new Date("2026-09-08T15:00:00.000Z");

  it("CAS-bumps ownershipRevision when a human fromMe arrives", () => {
    expect(
      humanFromMeOwnershipCas({
        conversationId: "conv-1",
        ownershipRevision: 2,
        botStatus: "HANDOFF_SENT",
        handoffAt: lastAt,
        lastAt,
      }),
    ).toEqual({
      where: {
        id: "conv-1",
        ownershipRevision: 2,
        botStatus: { notIn: ["HUMAN_ACTIVE", "HUMAN_CLOSED"] },
      },
      data: {
        botStatus: "HUMAN_ACTIVE",
        handoffAt: lastAt,
        ownershipRevision: { increment: 1 },
      },
    });
  });

  it("does not set assumedByUserId — device fromMe has no CRM user", () => {
    const patch = humanFromMeOwnershipCas({
      conversationId: "conv-1",
      ownershipRevision: 2,
      botStatus: "BOT_ACTIVE",
      handoffAt: null,
      lastAt,
    });
    expect(patch?.data).not.toHaveProperty("assumedByUserId");
  });

  it("does not treat an already human or closed thread as a new assume", () => {
    expect(
      humanFromMeOwnershipCas({
        conversationId: "conv-1",
        ownershipRevision: 3,
        botStatus: "HUMAN_ACTIVE",
        handoffAt: lastAt,
        lastAt,
      }),
    ).toBeNull();
    expect(
      humanFromMeOwnershipCas({
        conversationId: "conv-1",
        ownershipRevision: 3,
        botStatus: "HUMAN_CLOSED",
        handoffAt: lastAt,
        lastAt,
      }),
    ).toBeNull();
  });
});
