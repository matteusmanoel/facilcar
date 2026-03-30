"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { cn } from "@/lib/cn";

interface BarChartProps {
  data: { label: string; value: number }[];
  color?: string;
  height?: number;
  className?: string;
  horizontal?: boolean;
}

export function BarChart({
  data,
  color = "#ff6600",
  height = 220,
  className,
  horizontal = false,
}: BarChartProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || data.length === 0) return;
    const chart = echarts.init(ref.current);

    const option: echarts.EChartsOption = horizontal
      ? {
          grid: { top: 8, right: 16, bottom: 8, left: 8, containLabel: true },
          xAxis: { type: "value", axisLabel: { fontSize: 11 }, splitLine: { lineStyle: { color: "#f4f4f5" } } },
          yAxis: {
            type: "category",
            data: data.map((d) => d.label),
            axisLabel: { fontSize: 11, color: "#71717a" },
            axisTick: { show: false },
            axisLine: { show: false },
          },
          series: [
            {
              type: "bar",
              data: data.map((d) => d.value),
              itemStyle: { color, borderRadius: [0, 4, 4, 0] },
              barMaxWidth: 24,
              label: { show: true, position: "right", fontSize: 11, color: "#71717a" },
            },
          ],
          tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        }
      : {
          grid: { top: 8, right: 16, bottom: 32, left: 8, containLabel: true },
          xAxis: {
            type: "category",
            data: data.map((d) => d.label),
            axisLabel: { fontSize: 10, color: "#71717a", rotate: data.length > 10 ? 30 : 0 },
            axisTick: { show: false },
            axisLine: { lineStyle: { color: "#e4e4e7" } },
          },
          yAxis: {
            type: "value",
            axisLabel: { fontSize: 11 },
            splitLine: { lineStyle: { color: "#f4f4f5" } },
            minInterval: 1,
          },
          series: [
            {
              type: "bar",
              data: data.map((d) => d.value),
              itemStyle: { color, borderRadius: [4, 4, 0, 0] },
              barMaxWidth: 32,
            },
          ],
          tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        };

    chart.setOption(option);

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);

    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [data, color, horizontal]);

  return (
    <div
      ref={ref}
      className={cn("w-full", className)}
      style={{ height }}
    />
  );
}

interface DonutChartProps {
  data: { label: string; value: number; color?: string }[];
  height?: number;
  className?: string;
}

const STATUS_COLORS: Record<string, string> = {
  Novo: "#3b82f6",
  "Em progresso": "#f59e0b",
  Contactado: "#8b5cf6",
  Qualificado: "#6366f1",
  Ganho: "#22c55e",
  Perdido: "#71717a",
  Spam: "#ef4444",
};

export function DonutChart({ data, height = 220, className }: DonutChartProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || data.length === 0) return;
    const chart = echarts.init(ref.current);

    chart.setOption({
      legend: {
        orient: "vertical",
        right: 0,
        top: "center",
        textStyle: { fontSize: 11, color: "#71717a" },
        icon: "circle",
        itemWidth: 8,
        itemHeight: 8,
      },
      series: [
        {
          type: "pie",
          radius: ["48%", "72%"],
          center: ["38%", "50%"],
          data: data.map((d) => ({
            name: d.label,
            value: d.value,
            itemStyle: { color: d.color ?? STATUS_COLORS[d.label] ?? "#e4e4e7" },
          })),
          label: { show: false },
          emphasis: {
            label: { show: true, fontSize: 12, fontWeight: "bold" },
          },
        },
      ],
      tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    });

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);

    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [data]);

  return (
    <div ref={ref} className={cn("w-full", className)} style={{ height }} />
  );
}
