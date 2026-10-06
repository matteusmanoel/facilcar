import { describe, expect, it } from "vitest";
import { isDirectVehicleImageUrl, isInvalidVehicleImageUrl } from "../vehicle-image-src";

describe("vehicle image source", () => {
  it("serves a public storage url directly", () => {
    const url =
      "https://oulknepjqhyiyjbiuqtg.supabase.co/storage/v1/object/public/vehicle-images/vehicles/a.png";
    expect(isDirectVehicleImageUrl(url)).toBe(true);
    expect(isInvalidVehicleImageUrl(url)).toBe(false);
  });

  it("treats empty, mock, and placeholder urls as missing", () => {
    expect(isInvalidVehicleImageUrl(null)).toBe(true);
    expect(isInvalidVehicleImageUrl("  ")).toBe(true);
    expect(isInvalidVehicleImageUrl("/mock/car.jpg")).toBe(true);
    expect(isInvalidVehicleImageUrl("/vehicle-placeholder.webp")).toBe(true);
    expect(isInvalidVehicleImageUrl("/no-image.svg")).toBe(true);
    expect(isDirectVehicleImageUrl("/mock/car.jpg")).toBe(false);
    expect(isDirectVehicleImageUrl(null)).toBe(false);
  });
});
