export default function EstoqueLoading() {
  return (
    <div className="min-h-screen animate-pulse py-5">
      <div className="w-full px-2 sm:px-3">
        <div className="flex flex-wrap gap-2">
          <div className="h-10 min-w-[180px] flex-1 rounded-lg bg-facil-border" />
          <div className="h-10 w-48 rounded-lg bg-facil-border" />
          <div className="h-10 w-36 rounded-lg bg-facil-border" />
          <div className="h-10 w-24 rounded-lg bg-facil-border" />
        </div>
        <div className="mt-3 h-3 w-24 rounded bg-facil-border" />
        <div className="mt-4 grid gap-3 sm:grid-cols-2 sm:gap-4 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="overflow-hidden rounded-2xl border border-facil-border bg-facil-card">
              <div className="aspect-[16/10] bg-facil-border" />
              <div className="space-y-3 p-5">
                <div className="h-10 w-3/4 rounded bg-facil-border" />
                <div className="h-7 w-1/2 rounded bg-facil-border" />
                <div className="h-6 w-full rounded bg-facil-border" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
