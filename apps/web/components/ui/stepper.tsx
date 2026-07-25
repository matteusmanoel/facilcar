"use client";

import { cn } from "@/lib/cn";
import { Check, AlertCircle } from "lucide-react";

interface StepperProps {
  steps: string[];
  currentStep: number;
  maxValidatedStep?: number;
  stepErrors?: Record<number, boolean>;
  onStepClick?: (index: number) => void;
  className?: string;
}

export function Stepper({
  steps,
  currentStep,
  maxValidatedStep = 0,
  stepErrors = {},
  onStepClick,
  className,
}: StepperProps) {
  return (
    <div className={cn("flex items-center", className)}>
      {steps.map((step, index) => {
        const isCompleted = index < currentStep;
        const isActive = index === currentStep;
        const isLast = index === steps.length - 1;
        const hasError = !!stepErrors[index];
        const isClickable = !!onStepClick;

        return (
          <div key={step} className="flex flex-1 items-center">
            <div className="flex flex-col items-center gap-1">
              <button
                type="button"
                disabled={!isClickable}
                onClick={() => isClickable && onStepClick(index)}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors",
                  hasError && "border-red-500 bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-400",
                  !hasError && isCompleted && "border-facil-orange bg-facil-orange text-white",
                  !hasError &&
                    isActive &&
                    "border-facil-orange bg-facil-card text-facil-orange",
                  !hasError &&
                    !isCompleted &&
                    !isActive &&
                    "border-facil-border bg-facil-card text-facil-muted",
                  isClickable && "cursor-pointer hover:scale-110",
                  !isClickable && "cursor-default",
                )}
              >
                {hasError ? (
                  <AlertCircle className="h-4 w-4" />
                ) : isCompleted ? (
                  <Check className="h-4 w-4" />
                ) : (
                  index + 1
                )}
              </button>
              <span
                className={cn(
                  "hidden text-xs font-medium sm:block",
                  hasError && "text-red-500",
                  !hasError && isActive && "text-facil-orange",
                  !hasError && isCompleted && "text-foreground",
                  !hasError && !isCompleted && !isActive && "text-facil-muted",
                )}
              >
                {step}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  "mx-2 h-0.5 flex-1 transition-colors",
                  isCompleted ? "bg-facil-orange" : "bg-facil-border",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
