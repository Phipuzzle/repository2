import { describe, expect, it } from "vitest";

import { chartSpecToOption } from "./echarts-adapter";
import type { ChartSpec } from "../../features/query-run/types";

const spec: ChartSpec = {
  type: "area",
  title: "月销售额",
  xField: "month",
  yField: "sales",
  dataset: [
    { month: "01月", sales: 1200 },
    { month: "02月", sales: 2400 },
  ],
};

describe("chartSpecToOption", () => {
  it("maps safe chart fields to ECharts axes and series", () => {
    const option = chartSpecToOption(spec);
    expect(option.xAxis).toMatchObject({
      type: "category",
      data: ["01月", "02月"],
    });
    expect(option.yAxis).toMatchObject({ type: "value" });
    expect(option.series).toMatchObject([
      { type: "line", data: [1200, 2400], areaStyle: { opacity: 0.18 } },
    ]);
  });
});
