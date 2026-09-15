import { describe, expect, it } from "vitest";
import {
  evaluatePhoneAccess,
  maskPhone,
  parseAllowlist,
} from "../phone-access";

const ALLOWED = "5511999000101";
const DENIED = "5511999000199";

describe("evaluatePhoneAccess", () => {
  it("rejects staging without allowlist", () => {
    const decision = evaluatePhoneAccess(ALLOWED, {
      environment: "staging",
      policy: "deny_all",
      allowlist: [],
    });
    expect(decision.allowed).toBe(false);
  });

  it("rejects staging with empty allowlist", () => {
    const decision = evaluatePhoneAccess(ALLOWED, {
      environment: "staging",
      policy: "allowlist",
      allowlist: [],
    });
    expect(decision.allowed).toBe(false);
  });

  it("allows an allowlisted number", () => {
    expect(
      evaluatePhoneAccess(ALLOWED, {
        environment: "staging",
        policy: "allowlist",
        allowlist: [ALLOWED],
      }).allowed,
    ).toBe(true);
  });

  it("denies a number outside the allowlist", () => {
    const decision = evaluatePhoneAccess(DENIED, {
      environment: "staging",
      policy: "allowlist",
      allowlist: [ALLOWED],
    });
    expect(decision.allowed).toBe(false);
    expect(decision.reason).not.toContain(DENIED);
  });

  it("normalizes equivalent formats", () => {
    expect(
      evaluatePhoneAccess("+55 11 99900-0101", {
        environment: "staging",
        policy: "allowlist",
        allowlist: parseAllowlist("5511999000101@s.whatsapp.net"),
      }).allowed,
    ).toBe(true);
  });

  it("denies invalid environment or policy", () => {
    expect(
      evaluatePhoneAccess(ALLOWED, {
        environment: "prod",
        policy: "allowlist",
        allowlist: [ALLOWED],
      }).allowed,
    ).toBe(false);
    expect(
      evaluatePhoneAccess(ALLOWED, {
        environment: "sandbox",
        policy: "open",
        allowlist: [ALLOWED],
      }).allowed,
    ).toBe(false);
  });

  it("does not treat production as unrestricted by default", () => {
    expect(
      evaluatePhoneAccess(ALLOWED, {
        environment: "production",
        policy: "deny_all",
        allowlist: [],
      }).allowed,
    ).toBe(false);
  });

  it("masks the full phone in logs", () => {
    const masked = maskPhone(ALLOWED);
    expect(masked).not.toContain(ALLOWED);
    expect(masked.endsWith("0101")).toBe(true);
    expect(masked).toContain("*");
  });
});
