"use client";

import Link from "next/link";
import { List, Columns3 } from "lucide-react";
import { cn } from "@/lib/cn";

interface ViewTabsProps {
  currentView: "lista" | "kanban";
}

export function ViewTabs({ currentView }: ViewTabsProps) {
  return (
    <div className="admin-tab-list">
      <Link
        href="/admin/leads"
        className={cn(
          "admin-tab",
          currentView === "lista" ? "admin-tab-active" : "admin-tab-inactive",
        )}
      >
        <List className="h-3.5 w-3.5" />
        Lista
      </Link>
      <Link
        href="/admin/leads?view=kanban"
        className={cn(
          "admin-tab",
          currentView === "kanban" ? "admin-tab-active" : "admin-tab-inactive",
        )}
      >
        <Columns3 className="h-3.5 w-3.5" />
        Kanban
      </Link>
    </div>
  );
}
