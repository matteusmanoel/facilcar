import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const prisma = vi.hoisted(() => ({
  message: {
    findUnique: vi.fn(),
    findFirst: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
  conversation: {
    upsert: vi.fn(),
    updateMany: vi.fn(),
  },
}));

vi.mock("@/lib/db", () => ({ prisma }));
vi.mock("@/features/customer/server/upsert", () => ({
  upgradeCustomerDisplayNameByPhone: vi.fn(),
}));

import { ingestSdrWebhook } from "../ingest";

const LAST_AT = new Date("2026-09-08T15:00:00.000Z");
const ALLOWED_JID = "5511999000101@s.whatsapp.net";
const DENIED_JID = "5511999000199@s.whatsapp.net";

function inboundPayload(jid: string, messageId: string) {
  return {
    event: "MESSAGES_UPSERT",
    instance: "facilcar-sdr",
    data: {
      key: { id: messageId, remoteJid: jid, fromMe: false },
      message: { conversation: "oi" },
      messageTimestamp: Math.floor(LAST_AT.getTime() / 1000),
    },
  };
}

describe("ingestSdrWebhook phone allowlist", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.SDR_ENVIRONMENT = "staging";
    process.env.SDR_OUTBOUND_POLICY = "allowlist";
    process.env.SDR_OUTBOUND_ALLOWLIST = "5511999000101";
    process.env.JULIA_ENABLED = "false";
    prisma.message.findUnique.mockResolvedValue(null);
    prisma.message.findFirst.mockResolvedValue(null);
    prisma.message.create.mockResolvedValue({ id: "msg-new" });
    prisma.conversation.upsert.mockResolvedValue({
      id: "conv-a",
      ownershipRevision: 0,
      botStatus: "BOT_ACTIVE",
      handoffAt: null,
    });
  });

  afterEach(() => {
    process.env.SDR_ENVIRONMENT = "sandbox";
    process.env.SDR_OUTBOUND_POLICY = "allowlist";
    process.env.SDR_OUTBOUND_ALLOWLIST = "5545988432998,5511999000101,5545999000000";
  });

  it("does not persist inbound for a phone outside the allowlist", async () => {
    const result = await ingestSdrWebhook(inboundPayload(DENIED_JID, "wa-denied-1"));
    expect(result.ok).toBe(true);
    expect(result.handled).toBe(0);
    expect(result.ignored).toBeGreaterThan(0);
    expect(result.reason).toBe("phone_not_allowed");
    expect(prisma.conversation.upsert).not.toHaveBeenCalled();
    expect(prisma.message.create).not.toHaveBeenCalled();
  });

  it("persists inbound for an allowlisted phone", async () => {
    const result = await ingestSdrWebhook(inboundPayload(ALLOWED_JID, "wa-ok-1"));
    expect(result.handled).toBe(1);
    expect(prisma.conversation.upsert).toHaveBeenCalled();
    expect(prisma.message.create).toHaveBeenCalled();
  });
});
