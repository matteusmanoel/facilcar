import { describe, expect, it } from "vitest";
import {
  normalizeRemoteJid,
  parseAllowedJids,
  isJidAllowed,
  isAnyJidAllowed,
  peerIdentityCandidates,
  preferredPeerJid,
  buildSessionKey,
} from "../normalize-jid";
import { classifyEvent, deterministicParseFromText } from "../classify";
import { validateVehicleImportInput } from "../validate";
import { extractInboundMessages } from "../evolution-parse";
import { sanitizePayload } from "../sanitize-payload";
import { assertCatalogImportSecret } from "../auth";
import type { NextRequest } from "next/server";

describe("normalizeRemoteJid + allowlist", () => {
  it("normalizes phone JIDs", () => {
    expect(normalizeRemoteJid("5545999974232@s.whatsapp.net")).toBe("5545999974232");
    expect(normalizeRemoteJid("5545999974232:12@s.whatsapp.net")).toBe("5545999974232");
  });

  it("allows listed JID and rejects others", () => {
    const allowed = parseAllowedJids("5545999974232, 5511999999999");
    expect(isJidAllowed(normalizeRemoteJid("5545999974232@s.whatsapp.net"), allowed)).toBe(true);
    expect(isJidAllowed(normalizeRemoteJid("5545888888888@s.whatsapp.net"), allowed)).toBe(false);
    expect(isJidAllowed("", allowed)).toBe(false);
    expect(isJidAllowed("5545999974232", parseAllowedJids(""))).toBe(false);
  });

  it("builds session key as instance|jid", () => {
    expect(buildSessionKey("facilcar", "5545999974232")).toBe("facilcar|5545999974232");
  });

  it("matches LID chats via remoteJidAlt phone", () => {
    const allowed = parseAllowedJids("5545988230845,554588230845");
    const candidates = peerIdentityCandidates(
      "245861426659479@lid",
      "554588230845@s.whatsapp.net",
    );
    expect(isAnyJidAllowed(candidates, allowed)).toBe(true);
    expect(preferredPeerJid(candidates)).toBe("554588230845");
  });
});

describe("classifyEvent", () => {
  it("marks vehicle headlines as VEHICLE_START", () => {
    expect(
      classifyEvent({
        text: "Honda Civic 2020 EXL\nR$ 98.900",
        hasMedia: false,
        rawPayload: {},
      }),
    ).toBe("VEHICLE_START");
  });

  it("marks price/km lines as CONTINUATION", () => {
    expect(classifyEvent({ text: "R$ 112.000", hasMedia: false, rawPayload: {} })).toBe(
      "CONTINUATION",
    );
    expect(classifyEvent({ text: "32.000 km", hasMedia: false, rawPayload: {} })).toBe(
      "CONTINUATION",
    );
    expect(classifyEvent({ text: "Automático", hasMedia: false, rawPayload: {} })).toBe(
      "CONTINUATION",
    );
  });

  it("marks media without text as MEDIA_ONLY", () => {
    expect(classifyEvent({ text: null, hasMedia: true, rawPayload: {} })).toBe("MEDIA_ONLY");
  });
});

type Kind = "VEHICLE_START" | "CONTINUATION" | "MEDIA_ONLY" | "UNKNOWN";

type SimEvent = { id: string; kind: Kind; text: string | null; hasMedia: boolean };

function simulateGroup(events: SimEvent[]) {
  const items: { id: string; texts: string[]; eventIds: string[] }[] = [];
  let open: (typeof items)[0] | null = null;
  const ignored: { id: string; reason: string }[] = [];

  for (const ev of events) {
    if (ev.kind === "VEHICLE_START") {
      if (open) open = null;
      const item = {
        id: `item-${items.length + 1}`,
        texts: [] as string[],
        eventIds: [] as string[],
      };
      if (ev.text) item.texts.push(ev.text);
      item.eventIds.push(ev.id);
      items.push(item);
      open = item;
      continue;
    }
    if (ev.kind === "CONTINUATION") {
      if (!open) {
        ignored.push({ id: ev.id, reason: "continuation_without_open_item" });
        continue;
      }
      if (ev.text) open.texts.push(ev.text);
      open.eventIds.push(ev.id);
      continue;
    }
    if (ev.kind === "MEDIA_ONLY") {
      if (!open) {
        ignored.push({ id: ev.id, reason: "orphan_media" });
        continue;
      }
      open.eventIds.push(ev.id);
      continue;
    }
    ignored.push({ id: ev.id, reason: "unknown_classification" });
  }
  return { items, ignored };
}

describe("grouper simulation", () => {
  it("continuation textual → 1 Item", () => {
    const msgs = [
      "Honda HR-V 2019",
      "R$ 112.000",
      "45.000 km",
      "Único dono",
    ];
    const events = msgs.map((text, i) => {
      const kind = classifyEvent({ text, hasMedia: false, rawPayload: {} });
      return { id: `e${i}`, kind, text, hasMedia: false };
    });
    const { items } = simulateGroup(events);
    expect(items).toHaveLength(1);
    expect(items[0]!.texts.join("\n")).toContain("Honda HR-V");
    expect(items[0]!.texts.join("\n")).toContain("R$ 112.000");
    expect(items[0]!.eventIds).toHaveLength(4);
  });

  it("dois veículos → 2 Items", () => {
    const events = [
      {
        id: "1",
        kind: classifyEvent({
          text: "Honda Civic EXL 2021",
          hasMedia: true,
          rawPayload: {},
        }),
        text: "Honda Civic EXL 2021",
        hasMedia: true,
      },
      {
        id: "2",
        kind: classifyEvent({ text: null, hasMedia: true, rawPayload: {} }),
        text: null,
        hasMedia: true,
      },
      {
        id: "3",
        kind: classifyEvent({
          text: "Toyota Corolla XEi 2020",
          hasMedia: true,
          rawPayload: {},
        }),
        text: "Toyota Corolla XEi 2020",
        hasMedia: true,
      },
      {
        id: "4",
        kind: classifyEvent({ text: null, hasMedia: true, rawPayload: {} }),
        text: null,
        hasMedia: true,
      },
    ];
    const { items } = simulateGroup(events);
    expect(items).toHaveLength(2);
    expect(items[0]!.texts[0]).toMatch(/Civic/);
    expect(items[1]!.texts[0]).toMatch(/Corolla/);
  });
});

describe("deterministic parse + validate", () => {
  it("parses headline fixture", () => {
    const parsed = deterministicParseFromText(
      "Honda Civic 2020\nR$ 98.900\n32.000 km\nAutomático",
    );
    expect(parsed.brand).toBe("Honda");
    expect(parsed.model).toBe("Civic");
    expect(parsed.priceCash).toBe("98900.00");
    expect(parsed.mileage).toBe(32000);
    const v = validateVehicleImportInput(parsed, parsed.description);
    expect(v.valid).toBe(true);
  });

  it("fails without identity", () => {
    const parsed = deterministicParseFromText("só preço R$ 10");
    parsed.title = null;
    parsed.brand = null;
    parsed.model = null;
    expect(validateVehicleImportInput(parsed, "x").valid).toBe(false);
  });

  it("rejects View as a real model", () => {
    const parsed = deterministicParseFromText("Toyota View 2016\nR$ 50.000");
    parsed.model = "View";
    const v = validateVehicleImportInput(parsed, parsed.description);
    expect(v.valid).toBe(false);
    expect(v.errors).toContain("suspicious_model");
  });

  it("rejects Não informado as a real model", () => {
    const parsed = deterministicParseFromText("Toyota Não informado 2016\nR$ 50.000");
    parsed.model = "Não informado";
    const v = validateVehicleImportInput(parsed, parsed.description);
    expect(v.valid).toBe(false);
    expect(v.errors).toContain("suspicious_model");
  });

  it("does not invent engine from ambiguous copy", () => {
    const parsed = deterministicParseFromText(
      "TOYOTA COROLLA GLI 1.8 ou 2.0 Automático\nR$ 70.000",
    );
    expect(parsed.engineDisplacementLiters).toBeNull();
    expect(parsed.warnings).toContain("ENGINE_AMBIGUOUS");
  });
});

describe("extractInboundMessages + composite key fields", () => {
  it("extracts fromMe messages with instance + messageId", () => {
    const payload = {
      instance: "facilcar",
      data: {
        key: {
          id: "ABC123",
          remoteJid: "5545999974232@s.whatsapp.net",
          fromMe: true,
        },
        message: { conversation: "Honda Civic 2020" },
        messageTimestamp: 1700000000,
      },
    };
    const msgs = extractInboundMessages(payload);
    expect(msgs).toHaveLength(1);
    expect(msgs[0]!.instance).toBe("facilcar");
    expect(msgs[0]!.messageId).toBe("ABC123");
    expect(msgs[0]!.fromMe).toBe(true);
  });

  it("extracts inbound productMessage with remoteJidAlt", () => {
    const msgs = extractInboundMessages({
      instance: "facilcar",
      data: {
        key: {
          id: "PROD1",
          fromMe: false,
          remoteJid: "245861426659479@lid",
          remoteJidAlt: "554588230845@s.whatsapp.net",
        },
        message: {
          productMessage: {
            product: {
              title: "TRACKER LTZ 1.8AT",
              description: "CHEVROLET TRACKER LTZ 2014",
            },
          },
        },
        messageTimestamp: 1700000000,
      },
    });
    expect(msgs).toHaveLength(1);
    expect(msgs[0]!.fromMe).toBe(false);
    expect(msgs[0]!.remoteJidAlt).toContain("554588230845");
    expect(msgs[0]!.text).toMatch(/TRACKER/i);
    expect(msgs[0]!.messageType).toBe("productMessage");
  });

  it("same messageId different instance are distinct keys", () => {
    const a = extractInboundMessages({
      instance: "facilcar",
      data: { key: { id: "SAME", fromMe: true, remoteJid: "1@s.whatsapp.net" }, message: { conversation: "A" } },
    })[0]!;
    const b = extractInboundMessages({
      instance: "other",
      data: { key: { id: "SAME", fromMe: true, remoteJid: "1@s.whatsapp.net" }, message: { conversation: "B" } },
    })[0]!;
    expect(`${a.instance}|${a.messageId}`).not.toBe(`${b.instance}|${b.messageId}`);
  });
});

describe("sanitizePayload", () => {
  it("redacts base64 and tokens", () => {
    const { sanitized, payloadHash } = sanitizePayload({
      base64: "aaaa".repeat(200),
      apikey: "secret",
      text: "ok",
    });
    const s = JSON.stringify(sanitized);
    expect(s).not.toContain("aaaa");
    expect(s).toContain("REDACTED");
    expect(payloadHash).toHaveLength(64);
  });
});

describe("assertCatalogImportSecret", () => {
  it("accepts Bearer and header secret", () => {
    process.env.CATALOG_IMPORT_SECRET = "test-secret";
    const mk = (headers: Record<string, string>) =>
      ({
        headers: { get: (k: string) => headers[k.toLowerCase()] ?? null },
      }) as unknown as NextRequest;

    expect(
      assertCatalogImportSecret(mk({ authorization: "Bearer test-secret" })),
    ).toBe(true);
    expect(
      assertCatalogImportSecret(mk({ "x-catalog-import-secret": "test-secret" })),
    ).toBe(true);
    expect(assertCatalogImportSecret(mk({ authorization: "Bearer wrong" }))).toBe(false);
  });
});
