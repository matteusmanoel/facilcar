import { describe, expect, it } from "vitest";
import { jpegUploadName, shouldReencodeVehiclePhoto } from "../prepare-vehicle-upload";

describe("prepareVehicleUpload", () => {
  it("reencodes photos and leaves gif and svg untouched", () => {
    expect(shouldReencodeVehiclePhoto("image/png")).toBe(true);
    expect(shouldReencodeVehiclePhoto("image/jpeg")).toBe(true);
    expect(shouldReencodeVehiclePhoto("image/webp")).toBe(true);
    expect(shouldReencodeVehiclePhoto("image/gif")).toBe(false);
    expect(shouldReencodeVehiclePhoto("image/svg+xml")).toBe(false);
  });

  it("names the stored file as jpeg", () => {
    expect(jpegUploadName("idea.PNG")).toBe("idea.jpg");
    expect(jpegUploadName("foto")).toBe("foto.jpg");
  });
});
