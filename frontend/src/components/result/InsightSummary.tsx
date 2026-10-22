import { Statistic, Typography } from "antd";
import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import type { QueryRun } from "../../features/query-run/types";

export function InsightSummary({ run }: { run: QueryRun }) {
  if (!run.result)
    return (
      <div className="result-empty">
        <Typography.Text type="secondary">
          完成查询后，这里会显示关键洞察。
        </Typography.Text>
      </div>
    );
  const numericFields = run.result.schema.filter(
    (field) => field.type === "number",
  );
  const preferred =
    numericFields.find((field) =>
      /sales|amount|revenue|total|金额|销售|收入/i.test(
        `${field.name} ${field.label}`,
      ),
    ) ??
    numericFields.find((field) => field.name === run.chartSpec?.yField) ??
    numericFields[0];
  const values = preferred
    ? run.result.rows
        .map((row) => Number(row[preferred.name]))
        .filter((value) => Number.isFinite(value))
    : [];
  const total = values.reduce((sum, value) => sum + value, 0);
  const first = values[0] ?? 0;
  const last = values.at(-1) ?? 0;
  const change = first === 0 ? 0 : ((last - first) / Math.abs(first)) * 100;
  const rising = change >= 0;
  return (
    <section className="insight-summary">
      <div>
        <Typography.Text type="secondary">分析结论</Typography.Text>
        <Typography.Paragraph className="insight-copy">
          {run.insight ||
            (run.result.total === 0
              ? "查询成功，但没有匹配的数据。"
              : "正在整理结果...")}
        </Typography.Paragraph>
      </div>
      <div className="kpi-grid">
        {preferred && values.length > 0 && (
          <Statistic
            title={`${preferred.label}合计`}
            value={total}
            precision={Number.isInteger(total) ? 0 : 2}
          />
        )}
        <Statistic title="数据行数" value={run.result.total} suffix="行" />
        {values.length > 1 && (
          <Statistic
            title="首末变化"
            value={Math.abs(change)}
            precision={1}
            prefix={rising ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
            suffix="%"
            valueStyle={{ color: rising ? "#389e0d" : "#cf1322" }}
          />
        )}
      </div>
    </section>
  );
}
