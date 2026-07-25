export default function PublicLoading() {
  return (
    <div className="animate-pulse">
      {/* Hero skeleton */}
      <div className="h-[480px] bg-zinc-900" />

      {/* Featured vehicles skeleton */}
      <section className="py-16 px-4">
        <div className="mx-auto max-w-6xl">
          <div className="mb-10 h-8 w-48 rounded-lg bg-facil-border" />
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="overflow-hidden rounded-2xl border border-facil-border bg-facil-card">
                <div className="aspect-[16/10] bg-facil-border" />
                <div className="p-4 space-y-2">
                  <div className="h-4 w-3/4 rounded bg-facil-border" />
                  <div className="h-6 w-1/2 rounded bg-facil-border" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
