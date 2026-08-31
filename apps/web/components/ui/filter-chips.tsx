"use client";

import { cn } from "@/lib/cn";

type ChipOption = { value: string; label: string };

type FilterChipsBase = {
  options: ChipOption[];
  disabled?: boolean;
  className?: string;
};

type MultiFilterChipsProps = FilterChipsBase & {
  multiple?: true;
  value: string[];
  onChange: (value: string[]) => void;
};

type SingleFilterChipsProps = FilterChipsBase & {
  multiple: false;
  value: string;
  onChange: (value: string) => void;
};

export type FilterChipsProps = MultiFilterChipsProps | SingleFilterChipsProps;

function chipClass(selected: boolean, disabled?: boolean) {
  return cn(
    "inline-flex h-8 items-center rounded-full border px-3 text-xs font-medium transition",
    selected
      ? "border-facil-orange bg-facil-orange text-white"
      : "border-facil-border bg-facil-card text-foreground hover:bg-facil-surface",
    disabled && "pointer-events-none opacity-50",
  );
}

export function FilterChips(props: FilterChipsProps) {
  const { options, disabled, className } = props;
  const isMulti = props.multiple !== false;

  function handleClick(optionValue: string) {
    if (disabled) return;
    if (isMulti) {
      const current = (props as MultiFilterChipsProps).value;
      const next = current.includes(optionValue)
        ? current.filter((v) => v !== optionValue)
        : [...current, optionValue];
      (props as MultiFilterChipsProps).onChange(next);
      return;
    }
    const current = (props as SingleFilterChipsProps).value;
    (props as SingleFilterChipsProps).onChange(current === optionValue ? "" : optionValue);
  }

  function isSelected(optionValue: string) {
    if (isMulti) return (props as MultiFilterChipsProps).value.includes(optionValue);
    return (props as SingleFilterChipsProps).value === optionValue;
  }

  return (
    <div className={cn("flex flex-wrap gap-1.5", className)} role="group">
      {options.map((option) => {
        const selected = isSelected(option.value);
        return (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            aria-pressed={selected}
            className={chipClass(selected, disabled)}
            onClick={() => handleClick(option.value)}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
