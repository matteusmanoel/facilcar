"use client";

import { cn } from "@/lib/cn";
import { Check } from "lucide-react";

interface StepperProps {
  steps: string[];
  currentStep: number;
  onStepClick?: (index: number) => void;
  className?: string;
}

export function Stepper({ steps, currentStep, onStepClick, className }: StepperProps) {
  return (
    <div className={cn("flex items-center", className)}>
      {steps.map((step, index) => {
        const isCompleted = index < currentStep;
        const isActive = index === currentStep;
        const isLast = index === steps.length - 1;
        const isClickable = onStepClick && index < currentStep;

        return (
          <div key={step} className="flex flex-1 items-center">
            <div className="flex flex-col items-center gap-1">
              <button
                type="button"
                disabled={!isClickable}
                onClick={() => isClickable && onStepClick(index)}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors",
                  isCompleted && "border-facil-orange bg-facil-orange text-white",
                  isActive && "border-facil-orange bg-white text-facil-orange dark:bg-zinc-900",
                  !isCompleted && !isActive && "border-zinc-300 bg-white text-zinc-400 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-500",
                  isClickable && "cursor-pointer hover:scale-110",
                  !isClickable && "cursor-default",
                )}
              >
                {isCompleted ? <Check className="h-4 w-4" /> : index + 1}
              </button>
              <span
                className={cn(
                  "hidden text-xs font-medium sm:block",
                  isActive && "text-facil-orange",
                  isCompleted && "text-zinc-700 dark:text-zinc-300",
                  !isCompleted && !isActive && "text-zinc-400 dark:text-zinc-500",
                )}
              >
                {step}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  "mx-2 h-0.5 flex-1 transition-colors",
                  isCompleted ? "bg-facil-orange" : "bg-zinc-200 dark:bg-zinc-700",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
