import { describe, expect, it } from "vitest";
import { rangeIds, toggleId, unionIds } from "@/lib/range-select";

describe("range-select", () => {
  const column = ["a", "b", "c", "d"];

  it("shift range uses ordered ids between anchor and target", () => {
    expect(rangeIds(column, "b", "d")).toEqual(["b", "c", "d"]);
    expect(rangeIds(column, "d", "b")).toEqual(["b", "c", "d"]);
  });

  it("falls back to the target when there is no anchor", () => {
    expect(rangeIds(column, null, "c")).toEqual(["c"]);
  });

  it("toggles membership without mutating the previous set", () => {
    const prev = new Set(["a"]);
    expect(toggleId(prev, "b")).toEqual(new Set(["a", "b"]));
    expect(toggleId(prev, "a")).toEqual(new Set());
    expect(prev).toEqual(new Set(["a"]));
  });

  it("unions ids for cmd/ctrl+A style select-all", () => {
    expect(unionIds(new Set(["a"]), column)).toEqual(new Set(column));
  });
});
