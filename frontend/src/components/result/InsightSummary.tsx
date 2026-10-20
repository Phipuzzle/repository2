import { Statistic, Typography } from "antd";
import { ArrowUpOutlined } from "@ant-design/icons";
import type { QueryRun } from "../../features/query-run/types";

export function InsightSummary({ run }: { run: QueryRun }) {
  if (!run.result) return <div className="result-empty"><Typography.Text type="secondary">完成查询后，这里会显示关键洞察。</Typography.Text></div>;
  const total = run.result.rows.reduce((sum, row) => sum + Number(row.sales ?? 0), 0);
  return <section className="insight-summary"><div><Typography.Text type="secondary">分析结论</Typography.Text><Typography.Paragraph className="insight-copy">{run.insight || "正在整理结果..."}</Typography.Paragraph></div><div className="kpi-grid"><Statistic title="累计销售额" value={total} precision={0} prefix="¥" /><Statistic title="数据行数" value={run.result.total} suffix="行" /><Statistic title="环比趋势" value={59} prefix={<ArrowUpOutlined />} suffix="%" valueStyle={{ color: "#389e0d" }} /></div></section>;
}
