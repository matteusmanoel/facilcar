export default function EstoqueLoading() {
  return (
    <div className="min-h-screen animate-pulse py-10 px-4">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <div className="border-b border-zinc-200 pb-8">
          <div className="h-9 w-32 rounded-lg bg-zinc-200" />
          <div className="mt-2 h-4 w-64 rounded bg-zinc-200" />
        </div>

        {/* Filter panel */}
        <div className="mt-8 h-48 rounded-2xl bg-zinc-200" />

        {/* Cards grid */}
        <div className="mt-8 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="overflow-hidden rounded-2xl border border-zinc-200 bg-white">
              <div className="aspect-[16/10] bg-zinc-200" />
              <div className="p-5 space-y-3">
                <div className="h-5 w-3/4 rounded bg-zinc-200" />
                <div className="h-7 w-1/2 rounded bg-zinc-200" />
                <div className="h-4 w-full rounded bg-zinc-200" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
