import { cn } from "@/lib/cn";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-zinc-300/70 dark:bg-zinc-700/45",
        className,
      )}
      {...props}
    />
  );
}

export { Skeleton };
