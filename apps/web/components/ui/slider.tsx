"use client";

import * as SliderPrimitive from "@radix-ui/react-slider";
import { cn } from "@/lib/cn";

type SliderProps = React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> & {
  thumbLabels?: string[];
};

function Slider({ className, thumbLabels, value, defaultValue, ...props }: SliderProps) {
  const thumbs = value ?? defaultValue ?? [0];

  return (
    <SliderPrimitive.Root
      value={value}
      defaultValue={defaultValue}
      className={cn(
        "relative flex w-full touch-none select-none items-center data-[disabled]:opacity-50",
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-facil-border">
        <SliderPrimitive.Range className="absolute h-full bg-facil-orange" />
      </SliderPrimitive.Track>
      {thumbs.map((_, i) => (
        <SliderPrimitive.Thumb
          key={i}
          aria-label={thumbLabels?.[i]}
          className="block h-4 w-4 rounded-full border border-facil-orange bg-facil-card shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-facil-orange focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        />
      ))}
    </SliderPrimitive.Root>
  );
}

export { Slider };
