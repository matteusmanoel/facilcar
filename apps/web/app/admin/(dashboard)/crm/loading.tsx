import { Skeleton } from "@/components/ui/skeleton";

export default function AdminCrmLoading() {
  return (
    <div className="admin-page admin-section space-y-4">
      <div className="space-y-2">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-4 w-56" />
      </div>
      <div className="flex gap-3 overflow-hidden pb-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-[420px] w-64 shrink-0 rounded-xl" />
        ))}
      </div>
    </div>
  );
}
