import { Button, Collapse, Descriptions, Divider, Tag, Typography } from "antd";
import { CopyOutlined, EyeOutlined } from "@ant-design/icons";
import type { QueryRun } from "../../features/query-run/types";

const statusLabel: Record<string, string> = { idle: "待查询", submitting: "提交中", streaming: "分析中", awaiting_clarification: "等待补充", awaiting_approval: "等待确认", completed: "已完成", failed: "失败", cancelled: "已取消" };

export function QueryInspector({ run, onClose }: { run: QueryRun; onClose: () => void }) {
  const copySql = () => { if (run.sql) void navigator.clipboard?.writeText(run.sql); };
  return <aside className="inspector-panel" aria-label="查询详情">
    <div className="panel-heading"><Typography.Text strong>查询详情</Typography.Text><Button type="text" icon={<EyeOutlined />} onClick={onClose} aria-label="关闭详情" /></div>
    <Descriptions column={1} size="small" items={[{ key: "status", label: "状态", children: <Tag color={run.status === "completed" ? "success" : run.status === "failed" ? "error" : "processing"}>{statusLabel[run.status]}</Tag> }, { key: "run", label: "运行 ID", children: run.id }, { key: "events", label: "事件数", children: run.events.length }]} />
    <Divider />
    <Collapse ghost items={[{ key: "sql", label: "SQL", extra: <Button type="text" size="small" icon={<CopyOutlined />} onClick={(event) => { event.stopPropagation(); copySql(); }} aria-label="复制 SQL" />, children: <pre className="sql-preview">{run.sql || "等待 SQL 生成"}</pre> }, { key: "metrics", label: "指标说明", children: <Typography.Paragraph type="secondary">销售额为有效订单实付金额之和；订单数按订单 ID 去重。</Typography.Paragraph> }, { key: "execution", label: "执行信息", children: <Descriptions column={1} size="small" items={[{ key: "model", label: "模型", children: "Mock Adapter" }, { key: "db", label: "数据源", children: "PostgreSQL Demo" }, { key: "latency", label: "耗时", children: run.completedAt ? "1.8s" : "-" }]} /> }]} />
  </aside>;
}
