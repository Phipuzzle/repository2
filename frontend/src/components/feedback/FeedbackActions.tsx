import { useState } from "react";
import {
  Button,
  Input,
  message,
  Modal,
  Space,
  Tooltip,
  Typography,
} from "antd";
import {
  DislikeOutlined,
  LikeOutlined,
  MessageOutlined,
} from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";

import { submitFeedback } from "../../features/query-run/api";

export function FeedbackActions({ runId }: { runId: string | null }) {
  const [feedback, setFeedback] = useState<"positive" | "negative" | null>(
    null,
  );
  const [isModalOpen, setModalOpen] = useState(false);
  const [comment, setComment] = useState("");
  const feedbackMutation = useMutation({
    mutationFn: ({
      rating,
      details,
    }: {
      rating: "positive" | "negative";
      details?: string;
    }) => {
      if (!runId) throw new Error("请先完成查询");
      return submitFeedback(runId, rating, details);
    },
    onSuccess: (_, variables) => {
      setFeedback(variables.rating);
      setModalOpen(false);
      setComment("");
      void message.success(variables.details ? "反馈已记录" : "感谢你的反馈");
    },
    onError: (error) => {
      void message.error(
        error instanceof Error ? error.message : "反馈提交失败",
      );
    },
  });
  const submitComment = () => {
    if (!comment.trim()) return;
    feedbackMutation.mutate({
      rating: feedback ?? "positive",
      details: comment,
    });
  };
  return (
    <>
      <div className="feedback-actions">
        <Typography.Text type="secondary">
          {feedback ? "感谢你的反馈" : "这个结果有帮助吗？"}
        </Typography.Text>
        <Space>
          <Tooltip title="结果正确">
            <Button
              size="small"
              type={feedback === "positive" ? "primary" : "default"}
              icon={<LikeOutlined />}
              aria-label="结果正确"
              disabled={!runId}
              onClick={() => {
                feedbackMutation.mutate({ rating: "positive" });
              }}
            />
          </Tooltip>
          <Tooltip title="结果错误">
            <Button
              size="small"
              danger={feedback === "negative"}
              type={feedback === "negative" ? "primary" : "default"}
              icon={<DislikeOutlined />}
              aria-label="结果错误"
              disabled={!runId}
              onClick={() => {
                feedbackMutation.mutate({ rating: "negative" });
              }}
            />
          </Tooltip>
          <Button
            size="small"
            icon={<MessageOutlined />}
            onClick={() => setModalOpen(true)}
            disabled={!runId}
          >
            补充反馈
          </Button>
        </Space>
      </div>
      <Modal
        title="补充反馈"
        open={isModalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={submitComment}
        okText="提交"
        cancelText="取消"
        okButtonProps={{
          disabled: !comment.trim(),
          loading: feedbackMutation.isPending,
        }}
      >
        <Input.TextArea
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          rows={4}
          maxLength={500}
          showCount
          placeholder="描述结果中需要改进的地方"
        />
      </Modal>
    </>
  );
}
