"use client";

import { useState } from "react";
import { Slider } from "@/components/ui/slider";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  filtersFromSliderValues,
  parsePriceInput,
  sliderValuesFromFilters,
  type PriceBounds,
} from "@/features/catalog/lib/price-range";
import { cn } from "@/lib/cn";

export function RangeSliderField({
  bounds,
  min,
  max,
  onMinChange,
  onMaxChange,
  step,
  formatValue,
  ariaLabel,
  thumbLabels,
  prefix,
  compact = false,
}: {
  bounds: PriceBounds;
  min: string;
  max: string;
  onMinChange: (value: string) => void;
  onMaxChange: (value: string) => void;
  step: number;
  formatValue: (value: number) => string;
  ariaLabel: string;
  thumbLabels: [string, string];
  prefix?: string;
  compact?: boolean;
}) {
  const sliderValue = sliderValuesFromFilters(bounds, parsePriceInput(min), parsePriceInput(max));
  const disabled = bounds.min >= bounds.max;
  const [dragging, setDragging] = useState(false);
  const [hoverOpen, setHoverOpen] = useState(false);
  const tooltip = `${formatValue(sliderValue[0])} – ${formatValue(sliderValue[1])}`;

  function handleSlider(next: number[]) {
    const lo = next[0] ?? bounds.min;
    const hi = next[1] ?? bounds.max;
    const filters = filtersFromSliderValues(bounds, [lo, hi]);
    onMinChange(filters.min);
    onMaxChange(filters.max);
  }

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip
        open={dragging || hoverOpen}
        onOpenChange={(open) => {
          if (!dragging) setHoverOpen(open);
        }}
      >
        <TooltipTrigger asChild>
          <div
            className={cn(
              "flex items-center gap-2 rounded-lg border border-facil-border bg-facil-card px-3",
              compact ? "h-10 w-[13.5rem] shrink-0" : "h-10 w-full",
            )}
            onPointerEnter={() => setHoverOpen(true)}
            onPointerLeave={() => {
              if (!dragging) setHoverOpen(false);
            }}
          >
            {prefix ? (
              <span className="shrink-0 text-[11px] font-semibold text-facil-muted">{prefix}</span>
            ) : null}
            <Slider
              className="flex-1"
              min={Math.min(bounds.min, bounds.max)}
              max={Math.max(bounds.min, bounds.max)}
              step={step}
              value={sliderValue}
              onValueChange={(next) => {
                setDragging(true);
                handleSlider(next);
              }}
              onValueCommit={() => setDragging(false)}
              minStepsBetweenThumbs={1}
              disabled={disabled}
              thumbLabels={thumbLabels}
              aria-label={ariaLabel}
            />
          </div>
        </TooltipTrigger>
        <TooltipContent side="top">{tooltip}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
