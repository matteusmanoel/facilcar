"use client";

import Link from "next/link";
import { List, Columns3 } from "lucide-react";
import { cn } from "@/lib/cn";

interface ViewTabsProps {
  currentView: "lista" | "kanban";
}

export function ViewTabs({ currentView }: ViewTabsProps) {
  return (
    <div className="flex items-center gap-1 rounded-lg border border-zinc-200 bg-zinc-50 p-1 dark:border-zinc-700 dark:bg-zinc-800/50">
      <Link
        href="/admin/leads"
        className={cn(
          "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
          currentView === "lista"
            ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100"
            : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200",
        )}
      >
        <List className="h-3.5 w-3.5" />
        Lista
      </Link>
      <Link
        href="/admin/leads?view=kanban"
        className={cn(
          "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
          currentView === "kanban"
            ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100"
            : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200",
        )}
      >
        <Columns3 className="h-3.5 w-3.5" />
        Kanban
      </Link>
    </div>
  );
}
