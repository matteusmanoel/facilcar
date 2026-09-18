import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

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
import { POST } from "@/app/api/webhooks/sdr/route";

const LAST_AT = new Date("2026-09-08T15:00:00.000Z");
const ALLOWED_JID = "5511999000101@s.whatsapp.net";
const DENIED = "5511999000199";
const DENIED_JID = `${DENIED}@s.whatsapp.net`;
const SECRET = "test-sdr-secret";

function inboundPayload(
  jid: string,
  messageId: string,
  message: Record<string, unknown> = { conversation: "texto nao autorizado" },
) {
  return {
    event: "MESSAGES_UPSERT",
    instance: "facilcar-sdr",
    data: {
      key: { id: messageId, remoteJid: jid, fromMe: false },
      message,
      messageTimestamp: Math.floor(LAST_AT.getTime() / 1000),
    },
  };
}

describe("ingestSdrWebhook phone allowlist", () => {
  const fetchMock = vi.fn();
  let infoSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    infoSpy = vi.spyOn(console, "info").mockImplementation(() => undefined);
    process.env.SDR_ENVIRONMENT = "staging";
    process.env.SDR_OUTBOUND_POLICY = "allowlist";
    process.env.SDR_OUTBOUND_ALLOWLIST = "5511999000101";
    process.env.JULIA_ENABLED = "true";
    process.env.SDR_API_URL = "http://127.0.0.1:9";
    process.env.SDR_WEBHOOK_SECRET = SECRET;
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
    infoSpy.mockRestore();
    vi.unstubAllGlobals();
    process.env.SDR_ENVIRONMENT = "sandbox";
    process.env.SDR_OUTBOUND_POLICY = "allowlist";
    process.env.SDR_OUTBOUND_ALLOWLIST = "5545988432998,5511999000101,5545999000000";
    process.env.JULIA_ENABLED = "false";
    delete process.env.SDR_API_URL;
  });

  it("does not persist inbound for a phone outside the allowlist", async () => {
    const result = await ingestSdrWebhook(inboundPayload(DENIED_JID, "wa-denied-1"));
    expect(result.ok).toBe(true);
    expect(result.handled).toBe(0);
    expect(result.ignored).toBeGreaterThan(0);
    expect(result.reason).toBe("phone_not_allowed");
    expect(prisma.conversation.upsert).not.toHaveBeenCalled();
    expect(prisma.message.create).not.toHaveBeenCalled();
    expect(prisma.message.findUnique).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("HTTP denied ingest is 200, ignored, and hides the phone", async () => {
    const req = new NextRequest("http://localhost/api/webhooks/sdr", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-sdr-secret": SECRET,
      },
      body: JSON.stringify(inboundPayload(DENIED_JID, "wa-denied-http")),
    });
    const res = await POST(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.handled).toBe(0);
    expect(body.reason).toBe("phone_not_allowed");
    expect(JSON.stringify(body)).not.toContain(DENIED);
    expect(prisma.conversation.upsert).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("logs a sanitized operational refusal", async () => {
    await ingestSdrWebhook(inboundPayload(DENIED_JID, "wa-denied-log"));
    expect(infoSpy).toHaveBeenCalled();
    const dumped = infoSpy.mock.calls.map((call) => JSON.stringify(call)).join(" ");
    expect(dumped).not.toContain(DENIED);
    expect(dumped).not.toContain("texto nao autorizado");
    expect(dumped.toLowerCase()).toMatch(/phone|allowlist|ignored/);
  });

  it("does not persist unauthorized media", async () => {
    const result = await ingestSdrWebhook(
      inboundPayload(DENIED_JID, "wa-denied-img", {
        imageMessage: { mimetype: "image/jpeg", caption: "foto nao autorizada" },
      }),
    );
    expect(result.ignored).toBeGreaterThan(0);
    expect(prisma.message.create).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not persist unauthorized documents", async () => {
    const result = await ingestSdrWebhook(
      inboundPayload(DENIED_JID, "wa-denied-doc", {
        documentMessage: { mimetype: "application/pdf", fileName: "cnh.pdf" },
      }),
    );
    expect(result.ignored).toBeGreaterThan(0);
    expect(prisma.message.create).not.toHaveBeenCalled();
  });

  it("does not persist unauthorized location or reply when parsed", async () => {
    const location = await ingestSdrWebhook(
      inboundPayload(DENIED_JID, "wa-denied-loc", {
        locationMessage: { degreesLatitude: -25.4, degreesLongitude: -49.2 },
      }),
    );
    const reply = await ingestSdrWebhook(
      inboundPayload(DENIED_JID, "wa-denied-reply", {
        extendedTextMessage: {
          text: "quero esse",
          contextInfo: { stanzaId: "stz-denied" },
        },
      }),
    );
    expect(location.ignored + reply.ignored).toBeGreaterThan(0);
    expect(prisma.message.create).not.toHaveBeenCalled();
    expect(prisma.conversation.upsert).not.toHaveBeenCalled();
  });

  it("persists inbound for an allowlisted phone", async () => {
    const result = await ingestSdrWebhook(inboundPayload(ALLOWED_JID, "wa-ok-1"));
    expect(result.handled).toBe(1);
    expect(prisma.conversation.upsert).toHaveBeenCalled();
    expect(prisma.message.create).toHaveBeenCalled();
  });
});
