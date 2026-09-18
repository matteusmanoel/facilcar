import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { evaluatePhoneAccess, parseAllowlist } from "../phone-access";

const vectorsPath = path.resolve(
  process.cwd(),
  "../sdr/tests/contracts/phone_access_vectors.json",
);

type Vector = {
  id: string;
  phone: string;
  environment: string;
  policy: string;
  allowlist_raw: string;
  allowed: boolean;
  reason: string;
};

describe("shared phone-access contract vectors", () => {
  const payload = JSON.parse(readFileSync(vectorsPath, "utf8")) as {
    vectors: Vector[];
  };

  it("loads the Python-owned contract file", () => {
    expect(payload.vectors.length).toBeGreaterThanOrEqual(15);
  });

  for (const vector of payload.vectors) {
    it(`matches Python for ${vector.id}`, () => {
      const decision = evaluatePhoneAccess(vector.phone, {
        environment: vector.environment,
        policy: vector.policy,
        allowlist: parseAllowlist(vector.allowlist_raw),
      });
      expect(decision.allowed).toBe(vector.allowed);
      expect(decision.reason).toBe(vector.reason);
    });
  }
});
