import { describe, expect, it } from "vitest";
import { interpretClaimCount } from "@/features/lead/server/claim-result";
import { canAccessSdrDocuments } from "../document-access";

describe("interpretClaimCount", () => {
  it("returns ok when exactly one row was updated", () => {
    expect(interpretClaimCount(1)).toEqual({ ok: true });
  });

  it("returns already_claimed when zero rows updated", () => {
    expect(interpretClaimCount(0)).toEqual({ ok: false, error: "already_claimed" });
  });
});

describe("canAccessSdrDocuments", () => {
  it("allows SUPER_ADMIN and ADMIN", () => {
    expect(canAccessSdrDocuments("SUPER_ADMIN")).toBe(true);
    expect(canAccessSdrDocuments("ADMIN")).toBe(true);
  });

  it("denies LEAD_MANAGER and EDITOR", () => {
    expect(canAccessSdrDocuments("LEAD_MANAGER")).toBe(false);
    expect(canAccessSdrDocuments("EDITOR")).toBe(false);
  });
});
