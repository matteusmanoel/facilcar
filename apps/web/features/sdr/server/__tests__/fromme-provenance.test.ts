import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  classifyFromMeProvenance,
  isReservedBotProviderId,
  pendingBotReservationWhere,
  shouldAssumeHumanFromMe,
} from "../fromme-provenance";

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

const CONV_A = "conv-a";
const CONV_B = "conv-b";
const LAST_AT = new Date("2026-09-08T15:00:00.000Z");

function fromMePayload(opts: {
  instance?: string;
  phoneJid?: string;
  messageId?: string;
  text?: string;
  fromMe?: boolean;
}) {
  const id = opts.messageId;
  return {
    event: "MESSAGES_UPSERT",
    instance: opts.instance ?? "facilcar-sdr",
    data: {
      key: {
        ...(id !== undefined ? { id } : {}),
        remoteJid: opts.phoneJid ?? "5545988432998@s.whatsapp.net",
        fromMe: opts.fromMe ?? true,
      },
      message: { conversation: opts.text ?? "oi do vendedor" },
      messageTimestamp: Math.floor(LAST_AT.getTime() / 1000),
    },
  };
}

function liveConversation(id: string) {
  return {
    id,
    ownershipRevision: 0,
    botStatus: "BOT_ACTIVE",
    handoffAt: null,
  };
}

describe("classifyFromMeProvenance", () => {
  it("D1 Júlia outbound with isBotSent is a bot echo, not an assume", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "wa-julia-1",
      existingIsBotSent: true,
    });
    expect(c).toEqual({ kind: "bot_echo", reason: "is_bot_sent" });
    expect(shouldAssumeHumanFromMe(c)).toBe(false);
  });

  it("D2 unmatched fromMe with a provider id is human", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "wa-seller-1",
    });
    expect(c).toEqual({ kind: "human", reason: "unmatched_from_me" });
    expect(shouldAssumeHumanFromMe(c)).toBe(true);
  });

  it("D4 known bot provider id is not human", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "wa-julia-1",
      knownBotProviderId: true,
    });
    expect(c).toEqual({ kind: "bot_echo", reason: "known_provider_id" });
    expect(shouldAssumeHumanFromMe(c)).toBe(false);
  });

  it("D5 missing or blank provider id does not change ownership", () => {
    expect(
      classifyFromMeProvenance({ fromMe: true, providerMessageId: "" }),
    ).toEqual({ kind: "insufficient", reason: "missing_provider_id" });
    expect(
      classifyFromMeProvenance({ fromMe: true, providerMessageId: "   " }),
    ).toEqual({ kind: "insufficient", reason: "missing_provider_id" });
    expect(
      classifyFromMeProvenance({ fromMe: true, providerMessageId: null }),
    ).toEqual({ kind: "insufficient", reason: "missing_provider_id" });
    expect(
      shouldAssumeHumanFromMe(
        classifyFromMeProvenance({ fromMe: true, providerMessageId: "" }),
      ),
    ).toBe(false);
  });

  it("F7 pending reservation is a bot echo, not an assume", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "wa-julia-echo",
      pendingBotReservation: true,
    });
    expect(c).toEqual({ kind: "bot_echo", reason: "pending_reservation" });
    expect(shouldAssumeHumanFromMe(c)).toBe(false);
  });

  it("F8 unmatched fromMe with a real id is still human", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "wa-seller-unmatched",
    });
    expect(c).toEqual({ kind: "human", reason: "unmatched_from_me" });
    expect(shouldAssumeHumanFromMe(c)).toBe(true);
  });

  it("reserved bot-pending ids are distinguishable from Evolution ids", () => {
    expect(isReservedBotProviderId("bot-pending-abc")).toBe(true);
    expect(isReservedBotProviderId("wa-seller-1")).toBe(false);
    expect(
      pendingBotReservationWhere({
        conversationId: CONV_A,
        instanceName: "facilcar-sdr",
        text: "Olá, sou a Júlia",
      }),
    ).toEqual({
      conversationId: CONV_A,
      instanceName: "facilcar-sdr",
      isBotSent: true,
      providerMessageId: { startsWith: "bot-pending-" },
      text: "Olá, sou a Júlia",
    });
    expect(
      pendingBotReservationWhere({
        conversationId: CONV_A,
        instanceName: "facilcar-sdr",
        text: "  ",
      }),
    ).toBeNull();
  });

  it("inbound is not fromMe human", () => {
    const c = classifyFromMeProvenance({
      fromMe: false,
      providerMessageId: "wa-in-1",
    });
    expect(c.kind).toBe("ignore");
    expect(shouldAssumeHumanFromMe(c)).toBe(false);
  });
});

describe("ingestSdrWebhook fromMe provenance", () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true });

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock.mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    process.env.JULIA_ENABLED = "true";
    process.env.SDR_API_URL = "http://sdr.test";
    prisma.conversation.updateMany.mockResolvedValue({ count: 1 });
    prisma.message.create.mockResolvedValue({ id: "msg-new" });
    prisma.message.findFirst.mockResolvedValue(null);
    prisma.message.update.mockResolvedValue({ id: "msg-pending" });
    prisma.conversation.upsert.mockResolvedValue(liveConversation(CONV_A));
  });

  it("D1 Júlia outbound with isBotSent / provider id does not assume HUMAN_ACTIVE", async () => {
    prisma.message.findUnique.mockResolvedValue({
      id: "msg-bot",
      conversationId: CONV_A,
      isBotSent: true,
    });

    const result = await ingestSdrWebhook(
      fromMePayload({ messageId: "wa-julia-1", text: "Olá, sou a Júlia" }),
    );

    expect(result.deduped).toBe(1);
    expect(result.handled).toBe(0);
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
    expect(prisma.message.create).not.toHaveBeenCalled();
  });

  it("D2 identified human outbound CAS-assumes HUMAN_ACTIVE on this conversation", async () => {
    prisma.message.findUnique.mockResolvedValue(null);

    const result = await ingestSdrWebhook(
      fromMePayload({ messageId: "wa-seller-1" }),
    );

    expect(result.handled).toBe(1);
    expect(prisma.conversation.updateMany).toHaveBeenCalledTimes(1);
    expect(prisma.conversation.updateMany).toHaveBeenCalledWith({
      where: {
        id: CONV_A,
        ownershipRevision: 0,
        botStatus: { notIn: ["HUMAN_ACTIVE", "HUMAN_CLOSED"] },
      },
      data: {
        botStatus: "HUMAN_ACTIVE",
        handoffAt: expect.any(Date),
        ownershipRevision: { increment: 1 },
      },
    });
    const data = prisma.conversation.updateMany.mock.calls[0][0].data as Record<
      string,
      unknown
    >;
    expect(data).not.toHaveProperty("assumedByUserId");
    expect(prisma.message.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          fromMe: true,
          isHumanSent: true,
          isBotSent: false,
          processingStatus: "DONE",
          providerMessageId: "wa-seller-1",
          conversationId: CONV_A,
        }),
      }),
    );
  });

  it("D3 Evolution duplicate echo does not assume a second time", async () => {
    prisma.message.findUnique.mockResolvedValue({
      id: "msg-human",
      conversationId: CONV_A,
      isBotSent: false,
    });

    const result = await ingestSdrWebhook(
      fromMePayload({ messageId: "wa-seller-1" }),
    );

    expect(result.deduped).toBe(1);
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
  });

  it("D4 known bot provider id is looked up on this instance and is not human", async () => {
    prisma.message.findUnique.mockResolvedValue({
      id: "msg-bot",
      conversationId: CONV_A,
      isBotSent: true,
    });

    await ingestSdrWebhook(
      fromMePayload({ instance: "facilcar-sdr", messageId: "wa-julia-1" }),
    );

    expect(prisma.message.findUnique).toHaveBeenCalledWith({
      where: {
        instanceName_providerMessageId: {
          instanceName: "facilcar-sdr",
          providerMessageId: "wa-julia-1",
        },
      },
      select: { id: true, conversationId: true, isBotSent: true },
    });
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
  });

  it("D5 message without sufficient provenance does not change ownership", async () => {
    prisma.message.findUnique.mockResolvedValue(null);

    const missingId = await ingestSdrWebhook(fromMePayload({}));
    expect(missingId.handled ?? 0).toBe(0);
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();

    const blank = await ingestSdrWebhook(fromMePayload({ messageId: "   " }));
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
    expect(blank.handled).toBe(1);
    expect(prisma.message.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          isHumanSent: false,
          isBotSent: false,
          processingStatus: "DONE",
        }),
      }),
    );
  });

  it("D6 event from another instance/phone does not assume this conversation", async () => {
    prisma.message.findUnique.mockResolvedValue(null);
    prisma.conversation.upsert.mockResolvedValue(liveConversation(CONV_B));

    await ingestSdrWebhook(
      fromMePayload({
        instance: "other-instance",
        phoneJid: "5545999000000@s.whatsapp.net",
        messageId: "wa-other-1",
      }),
    );

    expect(prisma.message.findUnique).toHaveBeenCalledWith(
      expect.objectContaining({
        where: {
          instanceName_providerMessageId: {
            instanceName: "other-instance",
            providerMessageId: "wa-other-1",
          },
        },
      }),
    );
    expect(prisma.conversation.upsert).toHaveBeenCalledWith(
      expect.objectContaining({
        where: {
          instanceName_phone: {
            instanceName: "other-instance",
            phone: "5545999000000",
          },
        },
      }),
    );
    expect(prisma.conversation.updateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({ id: CONV_B }),
      }),
    );
    const where = prisma.conversation.updateMany.mock.calls[0][0].where as {
      id: string;
    };
    expect(where.id).not.toBe(CONV_A);
  });

  it("D8 human fromMe does not notify the worker / trigger auto-reply", async () => {
    prisma.message.findUnique.mockResolvedValue(null);

    await ingestSdrWebhook(fromMePayload({ messageId: "wa-seller-2" }));

    expect(prisma.conversation.updateMany).toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("D8 inbound still notifies the worker", async () => {
    prisma.message.findUnique.mockResolvedValue(null);

    await ingestSdrWebhook(
      fromMePayload({
        messageId: "wa-in-1",
        fromMe: false,
        text: "quero o civic",
      }),
    );

    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalled();
    expect(prisma.message.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          fromMe: false,
          isHumanSent: false,
          processingStatus: "PENDING",
        }),
      }),
    );
  });

  it("F7 echo matching a bot-pending reservation does not assume HUMAN_ACTIVE", async () => {
    prisma.message.findUnique.mockResolvedValue(null);
    prisma.message.findFirst.mockResolvedValue({ id: "msg-pending" });
    prisma.message.update.mockResolvedValue({ id: "msg-pending" });

    const result = await ingestSdrWebhook(
      fromMePayload({
        messageId: "wa-julia-echo",
        text: "Olá, sou a Júlia da FacilCar.",
      }),
    );

    expect(result.deduped).toBe(1);
    expect(result.handled).toBe(0);
    expect(prisma.message.findFirst).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          conversationId: CONV_A,
          instanceName: "facilcar-sdr",
          isBotSent: true,
          providerMessageId: { startsWith: "bot-pending-" },
          text: "Olá, sou a Júlia da FacilCar.",
        }),
      }),
    );
    expect(prisma.message.update).toHaveBeenCalledWith({
      where: { id: "msg-pending" },
      data: { providerMessageId: "wa-julia-echo" },
    });
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
    expect(prisma.message.create).not.toHaveBeenCalled();
  });

  it("F8 real human fromMe with unmatched id still assumes", async () => {
    prisma.message.findUnique.mockResolvedValue(null);
    prisma.message.findFirst.mockResolvedValue(null);

    const result = await ingestSdrWebhook(
      fromMePayload({
        messageId: "wa-seller-real",
        text: "vou atender daqui",
      }),
    );

    expect(result.handled).toBe(1);
    expect(prisma.conversation.updateMany).toHaveBeenCalledTimes(1);
    expect(prisma.message.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          fromMe: true,
          isHumanSent: true,
          isBotSent: false,
          providerMessageId: "wa-seller-real",
        }),
      }),
    );
  });
});
