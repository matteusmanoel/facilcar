"use client";

import dynamic from "next/dynamic";

const BarChart = dynamic(() => import("./AdminChart").then((m) => m.BarChart), {
  ssr: false,
  loading: () => (
    <div className="flex h-[220px] items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-facil-orange border-t-transparent" />
    </div>
  ),
});

const DonutChart = dynamic(() => import("./AdminChart").then((m) => m.DonutChart), {
  ssr: false,
  loading: () => (
    <div className="flex h-[220px] items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-facil-orange border-t-transparent" />
    </div>
  ),
});

interface ChartData {
  label: string;
  value: number;
}

interface DashboardChartsProps {
  periodTitle: string;
  periodData: ChartData[];
  statusData: ChartData[];
  sourceData: ChartData[];
}

export function DashboardCharts({
  periodTitle,
  periodData,
  statusData,
  sourceData,
}: DashboardChartsProps) {
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-5">
        <div className="admin-card lg:col-span-3">
          <h2 className="mb-4 text-sm font-semibold text-zinc-700 dark:text-zinc-200">{periodTitle}</h2>
          {periodData.some((d) => d.value > 0) ? (
            <BarChart data={periodData} />
          ) : (
            <div className="flex h-[220px] items-center justify-center text-sm text-zinc-400">
              Sem dados no período
            </div>
          )}
        </div>
        <div className="admin-card lg:col-span-2">
          <h2 className="mb-4 text-sm font-semibold text-zinc-700 dark:text-zinc-200">Leads por status</h2>
          {statusData.length > 0 ? (
            <DonutChart data={statusData} />
          ) : (
            <div className="flex h-[220px] items-center justify-center text-sm text-zinc-400">
              Sem dados
            </div>
          )}
        </div>
      </div>

      <div className="admin-card">
        <h2 className="mb-4 text-sm font-semibold text-zinc-700 dark:text-zinc-200">Origem dos leads</h2>
        {sourceData.length > 0 ? (
          <BarChart data={sourceData} height={180} horizontal />
        ) : (
          <div className="flex h-[180px] items-center justify-center text-sm text-zinc-400">
            Sem dados
          </div>
        )}
      </div>
    </>
  );
}
