"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { List, Columns3 } from "lucide-react";
import { cn } from "@/lib/cn";

interface ViewTabsProps {
  currentView: "lista" | "kanban";
}

export function ViewTabs({ currentView }: ViewTabsProps) {
  const searchParams = useSearchParams();

  function buildHref(view: "lista" | "kanban") {
    const sp = new URLSearchParams(searchParams.toString());
    if (view === "kanban") sp.set("view", "kanban");
    else sp.delete("view");
    const qs = sp.toString();
    return qs ? `/admin/leads?${qs}` : "/admin/leads";
  }

  return (
    <div className="admin-tab-list">
      <Link
        href={buildHref("lista")}
        className={cn(
          "admin-tab",
          currentView === "lista" ? "admin-tab-active" : "admin-tab-inactive",
        )}
      >
        <List className="h-3.5 w-3.5" />
        Lista
      </Link>
      <Link
        href={buildHref("kanban")}
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
