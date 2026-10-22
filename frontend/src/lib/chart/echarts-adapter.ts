import type { EChartsOption } from "echarts";

import type { ChartSpec } from "../../features/query-run/types";

/** Convert the backend-safe ChartSpec contract into an ECharts option. */
export function chartSpecToOption(spec: ChartSpec): EChartsOption {
  const categories = spec.dataset.map((item) =>
    String(item[spec.xField] ?? ""),
  );
  const values = spec.dataset.map((item) => Number(item[spec.yField] ?? 0));
  const isArea = spec.type === "area";

  return {
    animationDuration: 280,
    aria: { enabled: true, decal: { show: false } },
    dataZoom:
      spec.dataset.length > 20
        ? [{ type: "inside" }, { type: "slider", height: 18, bottom: 4 }]
        : undefined,
    grid: { top: 24, right: 20, bottom: 36, left: 56, containLabel: true },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: categories,
      boundaryGap: spec.type === "bar",
      axisLabel: { color: "#667384" },
      axisLine: { lineStyle: { color: "#e7ebf0" } },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        color: "#667384",
        formatter: (value: number) =>
          Math.abs(value) >= 1000
            ? `${Math.round(value / 1000)}k`
            : String(value),
      },
      splitLine: { lineStyle: { color: "#eef1f5" } },
    },
    series: [
      {
        name: spec.title,
        type: isArea || spec.type === "line" ? "line" : "bar",
        data: values,
        smooth: isArea || spec.type === "line",
        areaStyle: isArea ? { opacity: 0.18 } : undefined,
        itemStyle: { color: "#1677ff" },
        lineStyle: { color: "#1677ff", width: 2 },
      },
    ],
  };
}
