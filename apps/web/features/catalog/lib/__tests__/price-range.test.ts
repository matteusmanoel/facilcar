import { describe, expect, it } from "vitest";
import {
  filtersFromSliderValues,
  parsePriceInput,
  priceSliderStep,
  sliderValuesFromFilters,
} from "../price-range";

const bounds = { min: 20_000, max: 180_000 };

describe("price-range", () => {
  it("parks thumbs at bounds when filters are empty", () => {
    expect(sliderValuesFromFilters(bounds)).toEqual([20_000, 180_000]);
  });

  it("clamps and orders inverted filters", () => {
    expect(sliderValuesFromFilters(bounds, 200_000, 10_000)).toEqual([20_000, 180_000]);
  });

  it("omits URL params when the range is the full stock span", () => {
    expect(filtersFromSliderValues(bounds, [20_000, 180_000])).toEqual({ min: "", max: "" });
  });

  it("emits only the side that left the bound", () => {
    expect(filtersFromSliderValues(bounds, [45_000, 180_000])).toEqual({
      min: "45000",
      max: "",
    });
    expect(filtersFromSliderValues(bounds, [20_000, 90_000])).toEqual({
      min: "",
      max: "90000",
    });
  });

  it("picks a coarser step on a wide price span", () => {
    expect(priceSliderStep(20_000, 180_000)).toBe(1_000);
    expect(priceSliderStep(10_000, 25_000)).toBe(100);
  });

  it("treats blank input as an unset filter", () => {
    expect(parsePriceInput("")).toBeUndefined();
    expect(parsePriceInput("  ")).toBeUndefined();
    expect(parsePriceInput("45000")).toBe(45_000);
  });
});
