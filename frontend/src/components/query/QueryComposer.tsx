import { useState } from "react";
import { Button, Input, Space, Tooltip, Typography } from "antd";
import { AudioOutlined, SendOutlined, StopOutlined } from "@ant-design/icons";
import type { QueryRunStatus } from "../../features/query-run/types";

interface QueryComposerProps {
  status: QueryRunStatus;
  onSubmit: (question: string, conversationId: string | null) => void;
  onCancel: () => void;
  onRetry: () => void;
  onRecompute?: () => void;
  conversationId?: string | null;
}

export function QueryComposer({
  status,
  onSubmit,
  onCancel,
  onRetry,
  onRecompute,
  conversationId = null,
}: QueryComposerProps) {
  const [value, setValue] = useState("");
  const busy = status === "submitting" || status === "streaming";
  const canRetry = status === "failed" || status === "cancelled";
  const submit = (nextConversationId: string | null) => {
    if (value.trim()) {
      onSubmit(value.trim(), nextConversationId);
      setValue("");
    }
  };
  const canFollowUp = status === "completed" && Boolean(conversationId);
  const submitLabel =
    status === "awaiting_clarification" ? "提交补充条件" : "开始分析";
  return (
    <section className="composer" aria-label="查询输入">
      <Typography.Text type="secondary">
        试试：查询今年各区域月销售额并生成趋势图
      </Typography.Text>
      <Input.TextArea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onPressEnter={(event) => {
          if (!event.shiftKey) {
            event.preventDefault();
            submit(canFollowUp ? conversationId : null);
          }
        }}
        placeholder="用自然语言描述你想了解的数据..."
        autoSize={{ minRows: 2, maxRows: 5 }}
        disabled={busy}
      />
      <Space className="composer-actions">
        <Tooltip title="语音输入">
          <Button
            type="text"
            icon={<AudioOutlined />}
            aria-label="语音输入"
            disabled
          />
        </Tooltip>
        {busy ? (
          <Button
            danger
            icon={<StopOutlined />}
            onClick={onCancel}
            aria-label="取消查询"
          >
            取消查询
          </Button>
        ) : canRetry ? (
          <Button onClick={onRetry} aria-label="重试">
            重试
          </Button>
        ) : canFollowUp ? (
          <>
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={() => submit(conversationId)}
              aria-label="追问"
            >
              追问
            </Button>
            <Button onClick={() => submit(null)} aria-label="新查询">
              新查询
            </Button>
            {onRecompute && (
              <Button onClick={onRecompute} aria-label="重新计算">
                重新计算
              </Button>
            )}
          </>
        ) : (
          <>
            {status === "completed" && onRecompute && (
              <Button onClick={onRecompute} aria-label="重新计算">
                重新计算
              </Button>
            )}
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={() => submit(null)}
              disabled={!value.trim()}
            >
              {submitLabel}
            </Button>
          </>
        )}
      </Space>
    </section>
  );
}
