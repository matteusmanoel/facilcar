import { Skeleton } from "@/components/ui/skeleton";

type AdminListPageSkeletonProps = {
  titleWidth?: string;
  subtitleWidth?: string;
  filterCount?: number;
  tableHeight?: string;
  showAction?: boolean;
};

export function AdminListPageSkeleton({
  titleWidth = "w-40",
  subtitleWidth = "w-64",
  filterCount = 2,
  tableHeight = "h-[400px]",
  showAction = true,
}: AdminListPageSkeletonProps) {
  return (
    <div className="admin-page admin-section space-y-4">
      <div className="flex justify-between">
        <div className="space-y-2">
          <Skeleton className={`h-8 ${titleWidth}`} />
          <Skeleton className={`h-4 ${subtitleWidth}`} />
        </div>
        {showAction ? <Skeleton className="h-9 w-24" /> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        <Skeleton className="h-9 w-full max-w-xs" />
        {Array.from({ length: filterCount }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-28" />
        ))}
      </div>
      <Skeleton className={`${tableHeight} w-full rounded-xl`} />
    </div>
  );
}

export function AdminFormPageSkeleton() {
  return (
    <div className="admin-page admin-section space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-72" />
      </div>
      <div className="space-y-4 rounded-xl border border-facil-border bg-facil-card p-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-full" />
          </div>
        ))}
        <div className="flex justify-end gap-2 pt-2">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-32" />
        </div>
      </div>
    </div>
  );
}
