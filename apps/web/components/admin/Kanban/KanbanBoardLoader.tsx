"use client";

import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/skeleton";
import type { KanbanLead } from "./KanbanCard";

const KanbanBoard = dynamic(() => import("./KanbanBoard").then((m) => m.KanbanBoard), {
  ssr: false,
  loading: () => (
    <div className="flex gap-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex w-64 shrink-0 flex-col gap-2">
          <Skeleton className="h-10 rounded-xl" />
          {Array.from({ length: 3 }).map((_, j) => (
            <Skeleton key={j} className="h-24 rounded-lg" />
          ))}
        </div>
      ))}
    </div>
  ),
});

export function KanbanBoardLoader({ initialLeads }: { initialLeads: KanbanLead[] }) {
  return <KanbanBoard initialLeads={initialLeads} />;
}
