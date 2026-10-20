import type { ChartSpec, MetricDefinition, QueryResult, SSEEvent } from "./types";

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function mockQueryResult(empty = false, restricted = false): QueryResult {
  const rows = empty
    ? []
    : [
        { month: "01月", region: "华东", sales: 128000, orders: 312 },
        { month: "02月", region: "华东", sales: 146500, orders: 348 },
        { month: "03月", region: "华东", sales: 162800, orders: 391 },
        { month: "04月", region: "华东", sales: 171200, orders: 420 },
        { month: "05月", region: "华东", sales: 189600, orders: 465 },
        { month: "06月", region: "华东", sales: 203400, orders: 502 },
      ];
  return {
    rows,
    total: rows.length,
    schema: [
      { name: "month", type: "string", label: "月份" },
      { name: "region", type: "string", label: "区域" },
      { name: "sales", type: "number", label: restricted ? "销售额（已脱敏）" : "销售额" },
      { name: "orders", type: "number", label: "订单数" },
    ],
  };
}

export function mockChartSpec(result = mockQueryResult()): ChartSpec {
  return {
    type: "line",
    title: "华东区域月销售额趋势",
    xField: "month",
    yField: "sales",
    dataset: result.rows,
  };
}

export function mockSql(question: string): string {
  const isOrders = /订单|order/i.test(question);
  return `SELECT\n  DATE_TRUNC('month', o.created_at) AS month,\n  r.name AS region,\n  SUM(${isOrders ? "o.total_amount" : "o.total_amount"}) AS sales,\n  COUNT(DISTINCT o.id) AS orders\nFROM analytics.demo_orders AS o\nJOIN analytics.demo_regions AS r ON r.id = o.region_id\nWHERE o.created_at >= DATE_TRUNC('year', CURRENT_DATE)\nGROUP BY month, r.name\nORDER BY month ASC\nLIMIT 100;`;
}

function baseEvents(): Array<Omit<SSEEvent, "id" | "timestamp">> {
  return [
    { type: "submitted", message: "已提交查询" },
    { type: "intent_detected", message: "已识别为销售趋势分析" },
    { type: "context_retrieved", message: "已检索指标定义和可访问字段" },
    { type: "sql_generated", message: "已生成候选 SQL" },
    { type: "sql_validated", message: "SQL 只读校验通过" },
    { type: "query_started", message: "正在查询 PostgreSQL" },
    { type: "result_preview", message: "已返回结果预览" },
    { type: "chart_spec_ready", message: "已生成图表配置" },
    { type: "run_completed", message: "查询完成" },
  ];
}

export async function* mockQueryEvents(question: string): AsyncGenerator<SSEEvent> {
  const normalized = question.toLowerCase();
  const mode = (normalized.includes("补充") || normalized.includes("clarify")) && !normalized.includes("已补充条件")
    ? "clarification"
    : (normalized.includes("确认") || normalized.includes("成本") || normalized.includes("approval")) && !normalized.includes("已确认执行")
      ? "approval"
      : normalized.includes("失败") || normalized.includes("error")
        ? "error"
        : normalized.includes("取消") || normalized.includes("cancel")
          ? "cancel"
          : "success";
  const events = mode === "success" ? baseEvents() : [
    { type: "submitted" as const, message: "已提交查询" },
    { type: "intent_detected" as const, message: "已识别查询意图" },
    ...(mode === "clarification" ? [{ type: "clarification_required" as const, message: "需要补充时间范围或区域" }] : []),
    ...(mode === "approval" ? [{ type: "approval_required" as const, message: "查询预计扫描较多数据，需要确认" }] : []),
    ...(mode === "error" ? [{ type: "sql_generated" as const, message: "已生成候选 SQL" }, { type: "query_failed" as const, message: "模拟数据库执行失败" }] : []),
    ...(mode === "cancel" ? [{ type: "query_started" as const, message: "正在查询 PostgreSQL" }, { type: "run_cancelled" as const, message: "查询已取消" }] : []),
  ];
  let eventId = 0;
  for (let index = 0; index < events.length; index += 1) {
    await wait(280);
    if (index === 3 && normalized.includes("重连")) {
      eventId += 1;
      yield { id: eventId, type: "reconnected", timestamp: new Date().toISOString(), message: "SSE 已重连，正在恢复事件" };
      await wait(180);
    }
    const event = events[index];
    eventId += 1;
    yield { id: eventId, ...event, timestamp: new Date().toISOString() };
  }
}

export async function mockQueryRun(question: string, onEvent: (event: SSEEvent) => void): Promise<void> {
  for await (const event of mockQueryEvents(question)) onEvent(event);
}

export function mockMetricDefinitions(): MetricDefinition[] {
  return [
    { name: "销售额", definition: "订单实付金额之和，不含取消订单。", source: "analytics.demo_orders.total_amount", updatedAt: "2026-10-20" },
    { name: "订单数", definition: "去重后的有效订单数量。", source: "analytics.demo_orders.id", updatedAt: "2026-10-20" },
  ];
}
