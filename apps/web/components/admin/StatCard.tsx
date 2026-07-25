import Link from "next/link";
import { cn } from "@/lib/cn";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: number | string;
  href?: string;
  linkLabel?: string;
  icon?: LucideIcon;
  variant?: "default" | "highlight" | "warning";
  trend?: { value: number; label: string };
}

export function StatCard({
  title,
  value,
  href,
  linkLabel,
  icon: Icon,
  variant = "default",
  trend,
}: StatCardProps) {
  return (
    <div
      className={cn(
        "admin-card transition-shadow hover:shadow-md",
        variant === "highlight" && "ring-1 ring-facil-orange/20",
        variant === "warning" && "border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/20",
      )}
    >
      <div className="flex items-start justify-between">
        <p
          className={cn(
            "text-sm font-medium",
            variant === "default" && "text-facil-muted",
            variant === "highlight" && "text-facil-muted",
            variant === "warning" && "text-amber-700 dark:text-amber-400",
          )}
        >
          {title}
        </p>
        {Icon && (
          <div
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-lg",
              variant === "default" && "bg-facil-surface text-facil-muted",
              variant === "highlight" && "bg-facil-orange-light text-facil-orange",
              variant === "warning" && "bg-amber-100 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400",
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>
      <p
        className={cn(
          "mt-2 text-3xl font-bold tabular-nums",
          variant === "default" && "text-foreground",
          variant === "highlight" && "text-facil-orange",
          variant === "warning" && "text-amber-800 dark:text-amber-300",
        )}
      >
        {value}
      </p>
      {trend && (
        <p className={cn("mt-1 text-xs", trend.value >= 0 ? "text-facil-orange" : "text-red-500")}>
          {trend.value >= 0 ? "↑" : "↓"} {Math.abs(trend.value)}% {trend.label}
        </p>
      )}
      {href && linkLabel && (
        <Link href={href} className="mt-3 block text-sm font-medium text-facil-orange hover:underline">
          {linkLabel} →
        </Link>
      )}
    </div>
  );
}
