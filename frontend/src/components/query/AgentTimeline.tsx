import { Alert, Empty, Steps, Tag, Typography } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  LinkOutlined,
} from "@ant-design/icons";
import type { QueryRun } from "../../features/query-run/types";

const labels: Record<string, string> = {
  submitted: "提交",
  agent_started: "启动 Agent",
  intent_detected: "识别意图",
  context_retrieved: "检索上下文",
  semantic_mapped: "语义映射",
  query_plan_ready: "生成计划",
  sql_generated: "生成 SQL",
  sql_validated: "校验 SQL",
  sql_authorized: "权限校验",
  cost_checked: "成本检查",
  query_started: "执行查询",
  result_preview: "结果预览",
  insight_ready: "分析结果",
  chart_spec_ready: "生成图表",
  run_completed: "完成",
  clarification_required: "补充条件",
  approval_required: "等待确认",
  approval_granted: "确认执行",
  query_failed: "执行失败",
  run_failed: "执行失败",
  run_cancelled: "已取消",
  reconnected: "已重连",
};

export function AgentTimeline({ run }: { run: QueryRun }) {
  if (run.events.length === 0)
    return (
      <div className="timeline-empty">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="提交问题后查看 Agent 执行过程"
        />
      </div>
    );
  const last = run.events[run.events.length - 1];
  const failed = run.status === "failed" || run.status === "cancelled";
  return (
    <section className="timeline-panel">
      <div className="section-title">
        <Typography.Text strong>Agent 时间线</Typography.Text>
        {run.reconnectCount > 0 && (
          <Tag icon={<LinkOutlined />} color="processing">
            已重连 {run.reconnectCount} 次
          </Tag>
        )}
      </div>
      {run.error && <Alert type="error" showIcon message={run.error} />}
      {run.clarification && (
        <Alert type="warning" showIcon message={run.clarification} />
      )}
      {run.status === "awaiting_approval" && run.approvalReason && (
        <Alert type="info" showIcon message={run.approvalReason} />
      )}
      <Steps
        direction="vertical"
        size="small"
        current={run.events.length - 1}
        items={run.events.map((event, index) => ({
          title: labels[event.type] ?? event.type,
          description: (
            <span>
              {event.message}
              <small>{new Date(event.timestamp).toLocaleTimeString()}</small>
            </span>
          ),
          status:
            index === run.events.length - 1 &&
            !failed &&
            run.status !== "completed"
              ? "process"
              : failed && index === run.events.length - 1
                ? "error"
                : "finish",
          icon:
            index === run.events.length - 1 &&
            !failed &&
            run.status !== "completed" ? (
              <LoadingOutlined />
            ) : failed && index === run.events.length - 1 ? (
              <CloseCircleOutlined />
            ) : (
              <CheckCircleOutlined />
            ),
        }))}
      />
      {last && run.status === "completed" && (
        <Typography.Text type="success">
          执行链路已完成，共 {run.events.length} 个事件。
        </Typography.Text>
      )}
    </section>
  );
}
