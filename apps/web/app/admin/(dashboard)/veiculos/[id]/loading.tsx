import { Skeleton } from "@/components/ui/skeleton";

export default function AdminVeiculoEditLoading() {
  return (
    <div className="mx-auto flex h-[calc(100dvh-8.5rem)] w-full max-w-7xl flex-col gap-3 overflow-hidden px-4 py-3 sm:px-6 md:h-dvh lg:px-8">
      <div className="space-y-2">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-8 w-64" />
      </div>
      <Skeleton className="min-h-0 w-full flex-1 rounded-xl" />
    </div>
  );
}
