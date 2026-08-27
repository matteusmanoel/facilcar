import { describe, expect, it } from "vitest";
import { buildCarJsonLd } from "@/lib/seo";

describe("buildCarJsonLd vehicleEngine", () => {
  const base = {
    title: "Toyota Corolla GLI",
    slug: "toyota-corolla-gli",
    brand: { name: "Toyota" },
  };

  it("omits vehicleEngine when displacement is null", () => {
    const json = buildCarJsonLd({ ...base, engineDisplacementLiters: null });
    expect(json.vehicleEngine).toBeUndefined();
  });

  it("emits EngineSpecification only from persisted liters", () => {
    const json = buildCarJsonLd({ ...base, engineDisplacementLiters: 2.0 });
    expect(json.vehicleEngine).toEqual({
      "@type": "EngineSpecification",
      engineDisplacement: {
        "@type": "QuantitativeValue",
        value: 2.0,
        unitCode: "LTR",
      },
    });
  });
});
