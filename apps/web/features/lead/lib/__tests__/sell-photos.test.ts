import { describe, expect, it } from "vitest";
import {
  collectSellPhotoUploads,
  inferSellPhotoContentType,
  isSellPhotoUpload,
  visibleSellPhotoUrls,
} from "../sell-photos";

const JPEG_HEADER = new Uint8Array([0xff, 0xd8, 0xff, 0xd9]);
const PNG_HEADER = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

describe("sell photo intake", () => {
  it("collects blobs from FormData even when they are not File instances", () => {
    const blob = new Blob([JPEG_HEADER], { type: "image/jpeg" });
    Object.defineProperty(blob, "name", { value: "carro.jpg" });
    const formData = new FormData();
    formData.append("photos", blob);
    formData.append("photos", "not-a-file");
    formData.append("name", "Ana");

    const uploads = collectSellPhotoUploads(formData);
    expect(uploads).toHaveLength(1);
    expect(isSellPhotoUpload(blob)).toBe(true);
    expect(uploads[0]?.size).toBe(JPEG_HEADER.byteLength);
  });

  it("ignores empty file inputs", () => {
    const formData = new FormData();
    formData.append("photos", new File([], "empty.jpg", { type: "image/jpeg" }));
    expect(collectSellPhotoUploads(formData)).toEqual([]);
  });

  it("infers jpeg from filename when the browser omits a mime type", () => {
    expect(
      inferSellPhotoContentType({ type: "", name: "frente.JPG" }, new Uint8Array([0, 1, 2])),
    ).toBe("image/jpeg");
    expect(inferSellPhotoContentType({ type: "image/jpg" }, new Uint8Array())).toBe("image/jpeg");
    expect(inferSellPhotoContentType({ name: "x.bin" }, PNG_HEADER)).toBe("image/png");
    expect(inferSellPhotoContentType({ name: "x.bin" }, new Uint8Array([0, 1, 2]))).toBeNull();
  });

  it("keeps only displayable photo urls", () => {
    expect(
      visibleSellPhotoUrls([
        "https://cdn.example/sell-leads/a.jpg",
        "javascript:alert(1)",
        "  ",
        "/vehicle-placeholder.webp",
      ]),
    ).toEqual(["https://cdn.example/sell-leads/a.jpg", "/vehicle-placeholder.webp"]);
  });
});
