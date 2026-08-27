import { describe, expect, it } from "vitest";
import {
  isGroupJid,
  normalizeSdrJid,
  sdrPeerCandidates,
  sdrPreferredPhone,
} from "../jid-guard";

describe("isGroupJid", () => {
  it("detects @g.us groups", () => {
    expect(isGroupJid("120363012345678901@g.us")).toBe(true);
    expect(isGroupJid("120363012345678901@G.US")).toBe(true);
  });

  it("rejects 1:1 and LID chats", () => {
    expect(isGroupJid("5545988432998@s.whatsapp.net")).toBe(false);
    expect(isGroupJid("123456789012345@lid")).toBe(false);
    expect(isGroupJid(null)).toBe(false);
    expect(isGroupJid(undefined)).toBe(false);
    expect(isGroupJid("")).toBe(false);
  });
});

describe("normalize helpers", () => {
  it("normalizeSdrJid strips server suffix", () => {
    expect(normalizeSdrJid("5545988432998@s.whatsapp.net")).toBe("5545988432998");
  });

  it("sdrPreferredPhone prefers remoteJidAlt phone over LID", () => {
    const phone = sdrPreferredPhone(
      "123456789012345@lid",
      "5545988432998@s.whatsapp.net",
    );
    expect(phone).toBe("5545988432998");
  });

  it("sdrPeerCandidates orders alt before primary", () => {
    const candidates = sdrPeerCandidates(
      "123456789012345@lid",
      "5545988432998@s.whatsapp.net",
    );
    expect(candidates[0]).toBe("5545988432998");
    expect(candidates).toContain("123456789012345");
  });
});
