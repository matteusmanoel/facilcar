"use client";

import { RangeSliderField } from "@/features/catalog/ui/RangeSliderField";
import { formatCatalogPrice, priceSliderStep, type PriceBounds } from "@/features/catalog/lib/price-range";

type PriceRangeFilterProps = {
  bounds: PriceBounds;
  min: string;
  max: string;
  onMinChange: (value: string) => void;
  onMaxChange: (value: string) => void;
};

export function PriceRangeFilter({
  bounds,
  min,
  max,
  onMinChange,
  onMaxChange,
}: PriceRangeFilterProps) {
  return (
    <RangeSliderField
      compact
      prefix="R$"
      bounds={bounds}
      min={min}
      max={max}
      onMinChange={onMinChange}
      onMaxChange={onMaxChange}
      step={priceSliderStep(bounds.min, bounds.max)}
      formatValue={formatCatalogPrice}
      ariaLabel="Faixa de preço"
      thumbLabels={["Preço mínimo", "Preço máximo"]}
    />
  );
}
