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

  it("accepts a real File when File is available", () => {
    const file = new File([JPEG_HEADER], "frente.jpg", { type: "image/jpeg" });
    expect(isSellPhotoUpload(file)).toBe(true);
    const formData = new FormData();
    formData.append("photos", file);
    const collected: ReturnType<typeof collectSellPhotoUploads> = collectSellPhotoUploads(formData);
    expect(collected).toHaveLength(1);
    expect(collected[0]?.name).toBe("frente.jpg");
  });

  it("accepts a structural upload that the server can actually read", () => {
    const upload = {
      size: JPEG_HEADER.byteLength,
      type: "image/jpeg",
      name: "estrutural.jpg",
      arrayBuffer: async () => JPEG_HEADER.buffer.slice(
        JPEG_HEADER.byteOffset,
        JPEG_HEADER.byteOffset + JPEG_HEADER.byteLength,
      ),
    };
    expect(isSellPhotoUpload(upload)).toBe(true);
  });

  it("rejects values that cannot be read as uploads", () => {
    expect(isSellPhotoUpload(null)).toBe(false);
    expect(isSellPhotoUpload(undefined)).toBe(false);
    expect(isSellPhotoUpload("https://cdn.example/a.jpg")).toBe(false);
    expect(isSellPhotoUpload(1)).toBe(false);
    expect(isSellPhotoUpload([])).toBe(false);
    expect(isSellPhotoUpload({})).toBe(false);
    expect(isSellPhotoUpload({ name: "a.jpg" })).toBe(false);
    expect(isSellPhotoUpload({ type: "image/jpeg" })).toBe(false);
    expect(isSellPhotoUpload({ size: 12 })).toBe(false);
    expect(isSellPhotoUpload({ size: 12, arrayBuffer: "not-a-function" })).toBe(false);
    expect(isSellPhotoUpload({ size: 0, arrayBuffer: async () => new ArrayBuffer(0) })).toBe(false);
  });

  it("preserves order of mixed FormData entries without inventing duplicates", () => {
    const first = new File([JPEG_HEADER], "a.jpg", { type: "image/jpeg" });
    const second = new File([PNG_HEADER], "b.png", { type: "image/png" });
    const formData = new FormData();
    formData.append("photos", first);
    formData.append("photos", "skip-me");
    formData.append("photos", second);
    const uploads = collectSellPhotoUploads(formData);
    expect(uploads.map((item) => item.name)).toEqual(["a.jpg", "b.png"]);
    expect(uploads).toHaveLength(2);
  });

  it("treats missing url lists as empty without dropping valid urls or changing order", () => {
    expect(visibleSellPhotoUrls(null)).toEqual([]);
    expect(visibleSellPhotoUrls(undefined)).toEqual([]);
    expect(visibleSellPhotoUrls(["", "   "])).toEqual([]);
    expect(
      visibleSellPhotoUrls([
        "https://cdn.example/1.jpg",
        "https://cdn.example/2.jpg",
        "https://cdn.example/1.jpg",
      ]),
    ).toEqual([
      "https://cdn.example/1.jpg",
      "https://cdn.example/2.jpg",
      "https://cdn.example/1.jpg",
    ]);
  });
});
