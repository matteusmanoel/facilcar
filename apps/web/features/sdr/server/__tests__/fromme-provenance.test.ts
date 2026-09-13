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
  it("correlated reservation echo is BOT_CONFIRMED", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "wa-julia-echo",
      pendingBotReservation: true,
      textMatchesReservation: true,
    });
    expect(c).toEqual({
      kind: "bot_echo",
      reason: "pending_reservation",
      authorship: "BOT_CONFIRMED",
    });
    expect(shouldAssumeHumanFromMe(c)).toBe(false);
  });

  it("real id with divergent reservation text is AMBIGUOUS_FROM_ME", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "wa-divergent",
      pendingBotReservation: true,
      textMatchesReservation: false,
    });
    expect(c).toEqual({
      kind: "ambiguous",
      reason: "divergent_text",
      authorship: "AMBIGUOUS_FROM_ME",
    });
    expect(shouldAssumeHumanFromMe(c)).toBe(false);
  });

  it("early reserved bot-pending id without correlation is ambiguous", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "bot-pending-early",
    });
    expect(c).toEqual({
      kind: "ambiguous",
      reason: "early_echo",
      authorship: "AMBIGUOUS_FROM_ME",
    });
    expect(shouldAssumeHumanFromMe(c)).toBe(false);
  });

  it("unmatched fromMe with a real id does not assume", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "wa-seller-1",
    });
    expect(c).toEqual({
      kind: "ambiguous",
      reason: "unmatched_from_me",
      authorship: "AMBIGUOUS_FROM_ME",
    });
    expect(shouldAssumeHumanFromMe(c)).toBe(false);
  });

  it("administrative Assumir is HUMAN_CONFIRMED", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "wa-seller-1",
      adminAssume: true,
    });
    expect(c).toEqual({
      kind: "human",
      reason: "admin_assume",
      authorship: "HUMAN_CONFIRMED",
    });
    expect(shouldAssumeHumanFromMe(c)).toBe(true);
  });

  it("D1 Júlia outbound with isBotSent is BOT_CONFIRMED", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "wa-julia-1",
      existingIsBotSent: true,
    });
    expect(c).toEqual({
      kind: "bot_echo",
      reason: "is_bot_sent",
      authorship: "BOT_CONFIRMED",
    });
    expect(shouldAssumeHumanFromMe(c)).toBe(false);
  });

  it("D4 known bot provider id is BOT_CONFIRMED", () => {
    const c = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "wa-julia-1",
      knownBotProviderId: true,
    });
    expect(c).toEqual({
      kind: "bot_echo",
      reason: "known_provider_id",
      authorship: "BOT_CONFIRMED",
    });
    expect(shouldAssumeHumanFromMe(c)).toBe(false);
  });

  it("missing or blank provider id is ambiguous and does not assume", () => {
    const missing = classifyFromMeProvenance({
      fromMe: true,
      providerMessageId: "",
    });
    expect(missing).toEqual({
      kind: "ambiguous",
      reason: "missing_provider_id",
      authorship: "AMBIGUOUS_FROM_ME",
    });
    expect(
      classifyFromMeProvenance({ fromMe: true, providerMessageId: "   " }),
    ).toEqual({
      kind: "ambiguous",
      reason: "missing_provider_id",
      authorship: "AMBIGUOUS_FROM_ME",
    });
    expect(
      classifyFromMeProvenance({ fromMe: true, providerMessageId: null }),
    ).toEqual({
      kind: "ambiguous",
      reason: "missing_provider_id",
      authorship: "AMBIGUOUS_FROM_ME",
    });
    expect(shouldAssumeHumanFromMe(missing)).toBe(false);
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

  it("inbound is not fromMe and does not assume", () => {
    const c = classifyFromMeProvenance({
      fromMe: false,
      providerMessageId: "wa-in-1",
    });
    expect(c).toEqual({
      kind: "ignore",
      reason: "not_from_me",
      authorship: "NOT_FROM_ME",
    });
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

  it("echo matching a bot-pending reservation is bot, not HUMAN_ACTIVE", async () => {
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

  it("echo with a real id and divergent reservation text is ambiguous", async () => {
    prisma.message.findUnique.mockResolvedValue(null);
    prisma.message.findFirst
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({
        id: "msg-pending",
        text: "Olá, sou a Júlia da FacilCar.",
      });

    const result = await ingestSdrWebhook(
      fromMePayload({
        messageId: "wa-divergent",
        text: "vou atender daqui",
      }),
    );

    expect(result.handled).toBe(1);
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
    expect(prisma.message.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          fromMe: true,
          isHumanSent: false,
          isBotSent: false,
          processingStatus: "DONE",
          turnFactsJson: {
            _sdr_fromme: {
              authorship: "AMBIGUOUS_FROM_ME",
              kind: "ambiguous",
              reason: "divergent_text",
            },
          },
        }),
      }),
    );
  });

  it("early reserved id without a live reservation does not assume", async () => {
    prisma.message.findUnique.mockResolvedValue(null);

    await ingestSdrWebhook(
      fromMePayload({
        messageId: "bot-pending-early",
        text: "Olá, sou a Júlia da FacilCar.",
      }),
    );

    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
    expect(prisma.message.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          isHumanSent: false,
          isBotSent: false,
          turnFactsJson: {
            _sdr_fromme: {
              authorship: "AMBIGUOUS_FROM_ME",
              kind: "ambiguous",
              reason: "early_echo",
            },
          },
        }),
      }),
    );
  });

  it("fromMe without correlation does not assume HUMAN_ACTIVE", async () => {
    prisma.message.findUnique.mockResolvedValue(null);

    const result = await ingestSdrWebhook(
      fromMePayload({ messageId: "wa-seller-1" }),
    );

    expect(result.handled).toBe(1);
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
    expect(prisma.message.create).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({
          fromMe: true,
          isHumanSent: false,
          isBotSent: false,
          processingStatus: "DONE",
          turnFactsJson: {
            _sdr_fromme: {
              authorship: "AMBIGUOUS_FROM_ME",
              kind: "ambiguous",
              reason: "unmatched_from_me",
            },
          },
        }),
      }),
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("bot retry of the same provider id does not assume", async () => {
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

  it("two nearby reservations do not correlate across conversations", async () => {
    prisma.message.findUnique.mockResolvedValue(null);
    prisma.conversation.upsert.mockResolvedValue(liveConversation(CONV_B));
    prisma.message.findFirst.mockResolvedValue(null);

    await ingestSdrWebhook(
      fromMePayload({
        instance: "other-instance",
        phoneJid: "5545999000000@s.whatsapp.net",
        messageId: "wa-other-1",
        text: "Olá, sou a Júlia da FacilCar.",
      }),
    );

    expect(prisma.message.findFirst).toHaveBeenCalledWith(
      expect.objectContaining({
        where: expect.objectContaining({
          conversationId: CONV_B,
          instanceName: "other-instance",
        }),
      }),
    );
    const where = prisma.message.findFirst.mock.calls[0][0].where as {
      conversationId: string;
    };
    expect(where.conversationId).not.toBe(CONV_A);
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
  });

  it("D1 known bot row is a bot echo and does not assume", async () => {
    prisma.message.findUnique.mockResolvedValue({
      id: "msg-bot",
      conversationId: CONV_A,
      isBotSent: true,
    });

    const result = await ingestSdrWebhook(
      fromMePayload({ messageId: "wa-julia-1", text: "Olá, sou a Júlia" }),
    );

    expect(result.deduped).toBe(1);
    expect(prisma.conversation.updateMany).not.toHaveBeenCalled();
  });

  it("duplicate Evolution echo does not assume a second time", async () => {
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

  it("message without sufficient provenance does not change ownership", async () => {
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

  it("inbound still notifies the worker", async () => {
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
});
