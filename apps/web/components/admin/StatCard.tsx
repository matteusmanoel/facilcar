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
        "rounded-xl border p-5 shadow-sm transition-shadow hover:shadow-md",
        variant === "default" && "bg-white border-zinc-200 dark:bg-zinc-900 dark:border-zinc-800",
        variant === "highlight" && "bg-white border-facil-orange/20 ring-1 ring-facil-orange/10 dark:bg-zinc-900 dark:border-facil-orange/30",
        variant === "warning" && "bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-900/50",
      )}
    >
      <div className="flex items-start justify-between">
        <p
          className={cn(
            "text-sm font-medium",
            variant === "default" && "text-zinc-500 dark:text-zinc-400",
            variant === "highlight" && "text-zinc-600 dark:text-zinc-400",
            variant === "warning" && "text-amber-700 dark:text-amber-400",
          )}
        >
          {title}
        </p>
        {Icon && (
          <div
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-lg",
              variant === "default" && "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
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
          variant === "default" && "text-zinc-900 dark:text-zinc-50",
          variant === "highlight" && "text-facil-orange",
          variant === "warning" && "text-amber-800 dark:text-amber-300",
        )}
      >
        {value}
      </p>
      {trend && (
        <p className={cn("mt-1 text-xs", trend.value >= 0 ? "text-green-600" : "text-red-500")}>
          {trend.value >= 0 ? "↑" : "↓"} {Math.abs(trend.value)}% {trend.label}
        </p>
      )}
      {href && linkLabel && (
        <Link
          href={href}
          className={cn(
            "mt-3 block text-sm font-medium hover:underline",
            variant === "highlight" || variant === "warning"
              ? "text-facil-orange"
              : "text-facil-orange",
          )}
        >
          {linkLabel} →
        </Link>
      )}
    </div>
  );
}
