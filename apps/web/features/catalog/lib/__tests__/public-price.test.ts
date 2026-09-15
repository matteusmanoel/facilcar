import { describe, expect, it } from "vitest";
import { formatPublicPrice, publicVehiclePrice } from "../public-price";

describe("publicVehiclePrice", () => {
  it("shows de/por when repasse is lower than the announced cash price", () => {
    expect(
      publicVehiclePrice({ priceCash: 74900, priceRetailAsIs: 69900 }),
    ).toEqual({ current: 69900, original: 74900, compare: true });
  });

  it("keeps a single announced price when there is no repasse", () => {
    expect(publicVehiclePrice({ priceCash: 74900 })).toEqual({
      current: 74900,
      original: null,
      compare: false,
    });
  });

  it("does not compare equal or higher repasse values", () => {
    expect(publicVehiclePrice({ priceCash: 74900, priceRetailAsIs: 74900 })).toEqual({
      current: 74900,
      original: null,
      compare: false,
    });
    expect(publicVehiclePrice({ priceCash: 74900, priceRetailAsIs: 80000 })).toEqual({
      current: 74900,
      original: null,
      compare: false,
    });
  });

  it("uses repasse alone when cash is missing", () => {
    expect(publicVehiclePrice({ priceRetailAsIs: "69900.00" })).toEqual({
      current: 69900,
      original: null,
      compare: false,
    });
  });

  it("formats BRL without inventing a value", () => {
    expect(formatPublicPrice(69900)).toBe("R$ 69.900");
    expect(publicVehiclePrice({})).toEqual({ current: null, original: null, compare: false });
  });
});
