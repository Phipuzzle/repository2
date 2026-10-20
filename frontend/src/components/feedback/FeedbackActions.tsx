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

export function FeedbackActions() {
  const [feedback, setFeedback] = useState<"positive" | "negative" | null>(
    null,
  );
  const [isModalOpen, setModalOpen] = useState(false);
  const [comment, setComment] = useState("");
  const submitComment = () => {
    if (!comment.trim()) return;
    setModalOpen(false);
    setComment("");
    void message.success("反馈已记录");
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
              onClick={() => {
                setFeedback("positive");
                void message.success("已标记为结果正确");
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
              onClick={() => {
                setFeedback("negative");
                void message.info("已标记为结果错误");
              }}
            />
          </Tooltip>
          <Button
            size="small"
            icon={<MessageOutlined />}
            onClick={() => setModalOpen(true)}
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
        okButtonProps={{ disabled: !comment.trim() }}
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
