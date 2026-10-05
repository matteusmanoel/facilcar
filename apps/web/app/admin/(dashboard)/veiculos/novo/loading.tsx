import { Skeleton } from "@/components/ui/skeleton";

export default function AdminVeiculoNovoLoading() {
  return (
    <div className="mx-auto flex h-[calc(100dvh-8.5rem)] w-full max-w-7xl flex-col px-4 py-3 sm:px-6 md:h-dvh lg:px-8">
      <Skeleton className="min-h-0 w-full flex-1 rounded-xl" />
    </div>
  );
}
