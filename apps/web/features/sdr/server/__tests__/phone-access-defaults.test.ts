import { afterEach, describe, expect, it } from "vitest";
import { evaluatePhoneAccessFromEnv, parseAllowlist } from "../phone-access";

describe("phone-access env defaults after neutralizing vitest injection", () => {
  const previous = {
    env: process.env.SDR_ENVIRONMENT,
    policy: process.env.SDR_OUTBOUND_POLICY,
    allowlist: process.env.SDR_OUTBOUND_ALLOWLIST,
  };

  afterEach(() => {
    process.env.SDR_ENVIRONMENT = previous.env;
    process.env.SDR_OUTBOUND_POLICY = previous.policy;
    process.env.SDR_OUTBOUND_ALLOWLIST = previous.allowlist;
  });

  it("defaults to deny_all when policy is unset", () => {
    delete process.env.SDR_OUTBOUND_POLICY;
    delete process.env.SDR_OUTBOUND_ALLOWLIST;
    process.env.SDR_ENVIRONMENT = "sandbox";
    const decision = evaluatePhoneAccessFromEnv("5511999000101");
    expect(decision.allowed).toBe(false);
    expect(decision.reason).toBe("deny_all");
  });

  it("staging without allowlist denies", () => {
    process.env.SDR_ENVIRONMENT = "staging";
    process.env.SDR_OUTBOUND_POLICY = "allowlist";
    delete process.env.SDR_OUTBOUND_ALLOWLIST;
    const decision = evaluatePhoneAccessFromEnv("5511999000101");
    expect(decision.allowed).toBe(false);
  });

  it("staging with empty allowlist denies", () => {
    process.env.SDR_ENVIRONMENT = "staging";
    process.env.SDR_OUTBOUND_POLICY = "allowlist";
    process.env.SDR_OUTBOUND_ALLOWLIST = "  ,  ";
    expect(parseAllowlist(process.env.SDR_OUTBOUND_ALLOWLIST)).toEqual([]);
    const decision = evaluatePhoneAccessFromEnv("5511999000101");
    expect(decision.allowed).toBe(false);
  });
});
