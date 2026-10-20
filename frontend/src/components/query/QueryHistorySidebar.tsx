import { useState } from "react";
import { Button, Empty, List, Tag, Typography } from "antd";
import {
  ClockCircleOutlined,
  DeleteOutlined,
  StarFilled,
  StarOutlined,
} from "@ant-design/icons";
import type { QueryHistoryItem } from "../../features/query-run/types";

interface QueryHistorySidebarProps {
  history: QueryHistoryItem[];
  favoriteIds?: string[];
  onSelect?: (item: QueryHistoryItem) => void;
  onClear?: () => void;
  onToggleFavorite?: (id: string) => void;
}

export function QueryHistorySidebar({
  history,
  favoriteIds = [],
  onSelect,
  onClear,
  onToggleFavorite,
}: QueryHistorySidebarProps) {
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const visibleHistory = favoritesOnly
    ? history.filter((item) => favoriteIds.includes(item.id))
    : history;
  return (
    <aside className="history-sidebar" aria-label="查询历史">
      <div className="panel-heading">
        <Typography.Text strong>查询历史</Typography.Text>
        <Button
          type="text"
          size="small"
          icon={favoritesOnly ? <StarFilled /> : <StarOutlined />}
          aria-label={favoritesOnly ? "显示全部历史" : "只看收藏"}
          onClick={() => setFavoritesOnly((value) => !value)}
        />
      </div>
      {visibleHistory.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={favoritesOnly ? "暂无收藏查询" : "暂无查询记录"}
        />
      ) : (
        <List
          size="small"
          dataSource={visibleHistory}
          renderItem={(item) => (
            <List.Item
              className="history-item"
              onClick={() => onSelect?.(item)}
            >
              <div className="history-item-copy">
                <Typography.Text ellipsis>{item.question}</Typography.Text>
                <span>
                  <ClockCircleOutlined />{" "}
                  {item.durationMs
                    ? `${(item.durationMs / 1000).toFixed(1)}s`
                    : "处理中"}
                </span>
              </div>
              <Tag
                color={
                  item.status === "completed"
                    ? "success"
                    : item.status === "failed"
                      ? "error"
                      : "default"
                }
              >
                {item.status === "completed"
                  ? "完成"
                  : item.status === "failed"
                    ? "失败"
                    : item.status}
              </Tag>
              <Button
                type="text"
                size="small"
                aria-label={
                  favoriteIds.includes(item.id) ? "取消收藏" : "收藏查询"
                }
                icon={
                  favoriteIds.includes(item.id) ? (
                    <StarFilled />
                  ) : (
                    <StarOutlined />
                  )
                }
                onClick={(event) => {
                  event.stopPropagation();
                  onToggleFavorite?.(item.id);
                }}
              />
            </List.Item>
          )}
        />
      )}
      {history.length > 0 && (
        <Button
          type="link"
          danger
          icon={<DeleteOutlined />}
          className="clear-history"
          onClick={onClear}
        >
          清理历史
        </Button>
      )}
    </aside>
  );
}
