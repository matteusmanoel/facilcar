import { catalogFullBleedClass } from "@/features/catalog/lib/shell";

function VehicleCardSkeleton() {
  return (
    <div className="vehicle-card pointer-events-none shadow-none">
      <div className="aspect-[4/3] bg-facil-border" />
      <div className="space-y-3 bg-white p-5 dark:bg-zinc-900/40">
        <div className="h-5 w-3/4 rounded bg-facil-border" />
        <div className="h-4 w-1/2 rounded bg-facil-border" />
        <div className="h-3 w-2/5 rounded bg-facil-border" />
        <div className="flex items-end justify-between pt-1">
          <div className="h-7 w-28 rounded bg-facil-border" />
          <div className="h-8 w-20 rounded-lg bg-facil-border" />
        </div>
      </div>
    </div>
  );
}

export function HomePageSkeleton() {
  return (
    <main aria-busy="true" aria-live="polite" className="animate-pulse">
      <span className="sr-only">Carregando a página inicial</span>

      <section className="bg-facil-black text-white">
        <div className="relative min-h-[40rem] overflow-hidden bg-zinc-900 max-md:min-h-[calc(100svh-3.5rem)] md:min-h-[44rem] lg:min-h-[48rem]">
          <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_top,rgba(0,0,0,0.72)_0%,rgba(0,0,0,0.28)_22%,transparent_42%)] md:bg-[linear-gradient(90deg,rgba(0,0,0,0.78)_0%,rgba(0,0,0,0.48)_22%,rgba(0,0,0,0.16)_42%,transparent_62%)]" />
          <div className="pointer-events-none absolute inset-x-0 top-0 h-44 bg-gradient-to-b from-black/75 via-black/40 to-transparent md:hidden" />

          <div className="relative flex min-h-[40rem] flex-col items-stretch justify-end pb-8 pt-16 max-md:min-h-[calc(100svh-3.5rem)] sm:pb-12 md:min-h-[44rem] md:items-start md:justify-center md:py-24 lg:min-h-[48rem]">
            <div className="absolute inset-x-0 top-6 z-10 flex justify-center px-5 md:static md:inset-auto md:justify-start md:px-0 md:pl-8 lg:pl-10">
              <div className="h-4 w-64 rounded bg-white/25 sm:h-6 sm:w-80 md:h-7 md:w-[22rem]" />
            </div>
            <div className="relative w-full px-3 sm:max-w-lg sm:px-6 md:max-w-xl md:pl-8 lg:max-w-2xl lg:pl-10">
              <div className="h-8 w-[92%] rounded bg-white/30 sm:h-12 md:h-14 lg:h-16" />
              <div className="mt-2 h-8 w-[58%] rounded bg-white/30 sm:mt-3 sm:h-12 md:h-14" />
              <div className="mt-5 h-14 w-full rounded-full bg-[#25D366]/45 sm:mt-9 sm:h-14 sm:w-80" />
            </div>
          </div>
        </div>

        <div className="relative overflow-hidden border-t border-white/10">
          <div className="grid w-full grid-cols-3 divide-x divide-white/10 border-b border-white/10 bg-white/5">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="px-3 py-5 sm:px-6 sm:py-7">
                <div className="mx-auto h-9 w-16 rounded bg-facil-orange/45 sm:h-11 sm:w-20" />
                <div className="mx-auto mt-2 h-2.5 w-24 rounded bg-white/15 sm:w-32" />
              </div>
            ))}
          </div>
          <div className="px-4 py-10 sm:px-6 sm:py-12">
            <div className="flex flex-wrap items-center justify-center gap-4">
              <div className="h-12 w-44 rounded-xl bg-facil-orange/50" />
              <div className="h-12 w-36 rounded-xl border-2 border-white/15 bg-white/10" />
            </div>
            <div className="mx-auto mt-10 flex max-w-xl flex-col gap-2 sm:flex-row">
              <div className="h-12 flex-1 rounded-xl border border-white/15 bg-white/8" />
              <div className="h-12 w-full rounded-xl bg-white/25 sm:w-24" />
            </div>
          </div>
        </div>
      </section>

      <section className="py-16 sm:py-20">
        <div className={catalogFullBleedClass}>
          <div className="flex flex-col items-center">
            <div className="h-3 w-28 rounded bg-facil-orange/40" />
            <div className="mt-3 h-8 w-64 rounded-lg bg-facil-border md:h-10 md:w-80" />
          </div>

          <div className="mt-10 hidden justify-center gap-4 overflow-hidden md:flex">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="w-[min(22rem,32vw)] shrink-0">
                <VehicleCardSkeleton />
              </div>
            ))}
          </div>

          <div className="relative mt-10 h-[68rem] overflow-hidden md:hidden">
            <div className="flex flex-col gap-4 px-1">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className={`w-[84%] max-w-sm ${i % 2 === 0 ? "self-start" : "self-end"} ${
                    i === 1 ? "translate-x-5" : i === 2 ? "-translate-x-4" : ""
                  }`}
                >
                  <VehicleCardSkeleton />
                </div>
              ))}
            </div>
          </div>

          <div className="mt-10 flex justify-center">
            <div className="h-12 w-full rounded-full bg-facil-orange/45 sm:w-64" />
          </div>
        </div>
      </section>

      <section className="border-y border-facil-border bg-facil-surface py-20 px-4">
        <div className="mx-auto max-w-6xl">
          <div className="mx-auto h-3 w-24 rounded bg-facil-orange/40" />
          <div className="mx-auto mt-3 h-8 w-72 rounded-lg bg-facil-border md:h-10 md:w-96" />
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="flex h-full flex-col rounded-2xl border border-facil-border bg-facil-card p-6"
              >
                <div className="flex gap-1">
                  {Array.from({ length: 5 }).map((_, j) => (
                    <div key={j} className="h-4 w-4 rounded bg-facil-border" />
                  ))}
                </div>
                <div className="mt-4 space-y-2">
                  <div className="h-4 w-full rounded bg-facil-border" />
                  <div className="h-4 w-5/6 rounded bg-facil-border" />
                </div>
                <div className="mt-5 flex items-center gap-3 border-t border-facil-border pt-4">
                  <div className="h-10 w-10 shrink-0 rounded-full bg-facil-orange/40" />
                  <div className="space-y-2">
                    <div className="h-3.5 w-24 rounded bg-facil-border" />
                    <div className="h-3 w-16 rounded bg-facil-border" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-facil-black py-20 px-4">
        <div className="mx-auto max-w-6xl">
          <div className="h-3 w-20 rounded bg-facil-orange/40" />
          <div className="mt-3 h-8 w-56 rounded-lg bg-white/15 md:h-10 md:w-72" />
          <div className="mt-10 grid gap-6 lg:grid-cols-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="rounded-2xl border border-white/10 bg-white/5 p-8">
                <div className="h-12 w-12 rounded-xl bg-facil-orange/20" />
                <div className="mt-5 h-7 w-40 rounded bg-white/20" />
                <div className="mt-3 space-y-2">
                  <div className="h-4 w-full rounded bg-white/10" />
                  <div className="h-4 w-4/5 rounded bg-white/10" />
                </div>
                <div className="mt-6 h-11 w-36 rounded-lg bg-facil-orange/45" />
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
