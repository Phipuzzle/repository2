import { Button, Collapse, Descriptions, Divider, Tag, Typography } from "antd";
import { CopyOutlined, EyeOutlined } from "@ant-design/icons";
import type {
  MetricDefinition,
  QueryRun,
} from "../../features/query-run/types";

const statusLabel: Record<string, string> = {
  idle: "待查询",
  submitting: "提交中",
  streaming: "分析中",
  awaiting_clarification: "等待补充",
  awaiting_approval: "等待确认",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

export function QueryInspector({
  run,
  metrics,
  onClose,
}: {
  run: QueryRun;
  metrics: MetricDefinition[];
  onClose: () => void;
}) {
  const copySql = () => {
    if (run.sql) void navigator.clipboard?.writeText(run.sql);
  };
  const model = [...run.events]
    .reverse()
    .find((event) => typeof event.data?.model === "string")?.data?.model;
  const startedAt = run.startedAt ? new Date(run.startedAt).getTime() : NaN;
  const completedAt = run.completedAt
    ? new Date(run.completedAt).getTime()
    : NaN;
  const latency =
    Number.isFinite(startedAt) && Number.isFinite(completedAt)
      ? `${((completedAt - startedAt) / 1000).toFixed(1)}s`
      : "-";
  const tokenUsage = run.usage?.total_tokens ?? 0;
  return (
    <aside className="inspector-panel" aria-label="查询详情">
      <div className="panel-heading">
        <Typography.Text strong>查询详情</Typography.Text>
        <Button
          type="text"
          icon={<EyeOutlined />}
          onClick={onClose}
          aria-label="关闭详情"
        />
      </div>
      <Descriptions
        column={1}
        size="small"
        items={[
          {
            key: "status",
            label: "状态",
            children: (
              <Tag
                color={
                  run.status === "completed"
                    ? "success"
                    : run.status === "failed"
                      ? "error"
                      : "processing"
                }
              >
                {statusLabel[run.status]}
              </Tag>
            ),
          },
          { key: "run", label: "运行 ID", children: run.id },
          { key: "events", label: "事件数", children: run.events.length },
        ]}
      />
      <Divider />
      <Collapse
        ghost
        items={[
          {
            key: "sql",
            label: "SQL",
            extra: (
              <Button
                type="text"
                size="small"
                icon={<CopyOutlined />}
                onClick={(event) => {
                  event.stopPropagation();
                  copySql();
                }}
                aria-label="复制 SQL"
              />
            ),
            children: (
              <pre className="sql-preview">{run.sql || "等待 SQL 生成"}</pre>
            ),
          },
          {
            key: "metrics",
            label: "指标说明",
            children:
              metrics.length > 0 ? (
                <Descriptions
                  column={1}
                  size="small"
                  items={metrics.map((metric) => ({
                    key: metric.name,
                    label: metric.name,
                    children: metric.definition,
                  }))}
                />
              ) : (
                <Typography.Paragraph type="secondary">
                  暂无可用的指标定义。
                </Typography.Paragraph>
              ),
          },
          {
            key: "execution",
            label: "执行信息",
            children: (
              <Descriptions
                column={1}
                size="small"
                items={[
                  {
                    key: "model",
                    label: "模型",
                    children:
                      typeof model === "string" ? model : "等待模型信息",
                  },
                  { key: "db", label: "数据源", children: "PostgreSQL" },
                  { key: "latency", label: "耗时", children: latency },
                  { key: "tokens", label: "Token", children: tokenUsage },
                ]}
              />
            ),
          },
        ]}
      />
    </aside>
  );
}
