"use client";

import { useEffect, useRef } from "react";
import { Empty, Typography } from "antd";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  AriaComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

import type { ChartSpec } from "../../features/query-run/types";
import { chartSpecToOption } from "../../lib/chart/echarts-adapter";

echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  AriaComponent,
  CanvasRenderer,
]);

export function ChartPanel({
  spec,
  emptyResult = false,
}: {
  spec: ChartSpec | null;
  emptyResult?: boolean;
}) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!spec || !chartRef.current) return undefined;
    const chart = echarts.init(chartRef.current, undefined, {
      renderer: "canvas",
    });
    chart.setOption(chartSpecToOption(spec));
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [spec]);

  if (!spec || spec.dataset.length === 0)
    return (
      <div className="result-empty">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={spec || emptyResult ? "没有可视化数据" : "等待图表数据"}
        />
      </div>
    );
  return (
    <section className="chart-panel">
      <div className="section-title">
        <Typography.Text strong>{spec.title}</Typography.Text>
        <Typography.Text type="secondary">
          {spec.type === "bar" ? "对比图" : "趋势图"}
        </Typography.Text>
      </div>
      <div
        ref={chartRef}
        className="chart-canvas"
        role="img"
        aria-label={spec.title}
      />
    </section>
  );
}
