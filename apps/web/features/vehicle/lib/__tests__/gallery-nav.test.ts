import { describe, expect, it } from "vitest";
import { wrapGalleryIndex } from "../gallery-nav";

describe("wrapGalleryIndex", () => {
  it("wraps forward past the last photo", () => {
    expect(wrapGalleryIndex(2, 3, 1)).toBe(0);
  });

  it("wraps backward before the first photo", () => {
    expect(wrapGalleryIndex(0, 3, -1)).toBe(2);
  });

  it("returns 0 when there are no photos", () => {
    expect(wrapGalleryIndex(0, 0, 1)).toBe(0);
  });
});
