"use client";

import { useState } from "react";
import { Button, Drawer, Layout, Space, Tabs, Typography } from "antd";
import { EyeOutlined } from "@ant-design/icons";
import { useQueryStore } from "../../features/query-run/store";
import { AppHeader } from "./AppHeader";
import { QueryHistorySidebar } from "../query/QueryHistorySidebar";
import { QueryComposer } from "../query/QueryComposer";
import { AgentTimeline } from "../query/AgentTimeline";
import { QueryInspector } from "../query/QueryInspector";
import { InsightSummary } from "../result/InsightSummary";
import { ChartPanel } from "../result/ChartPanel";
import { DataTable } from "../result/DataTable";
import { SqlViewer } from "../result/SqlViewer";
import { FeedbackActions } from "../feedback/FeedbackActions";

const { Content } = Layout;

export function AppShell() {
  const [isMobileInspectorOpen, setMobileInspectorOpen] = useState(false);
  const {
    current,
    history,
    favoriteIds,
    activeResultTab,
    isInspectorOpen,
    isHistoryOpen,
    setActiveResultTab,
    setInspectorOpen,
    setHistoryOpen,
    selectHistory,
    clearHistory,
    toggleFavorite,
    reset,
    submit,
    cancel,
    retry,
    approve,
    clarify,
  } = useQueryStore();
  const resultItems = [
    {
      key: "overview",
      label: "概览",
      children: <InsightSummary run={current} />,
    },
    {
      key: "chart",
      label: "图表",
      children: <ChartPanel spec={current.chartSpec} />,
    },
    {
      key: "table",
      label: "数据表",
      children: <DataTable result={current.result} />,
    },
    { key: "sql", label: "SQL", children: <SqlViewer sql={current.sql} /> },
  ];
  const historyPanel = (
    <QueryHistorySidebar
      history={history}
      favoriteIds={favoriteIds}
      onSelect={(item) => selectHistory(item.id)}
      onClear={clearHistory}
      onToggleFavorite={toggleFavorite}
    />
  );
  return (
    <Layout className="app-layout">
      <AppHeader onNew={reset} onHistory={() => setHistoryOpen(true)} />
      <Layout>
        <div className="desktop-history">{historyPanel}</div>
        <Content className="workspace-content">
          <main className="workspace-main">
            <div className="workspace-title">
              <div>
                <Typography.Title level={2}>数据分析工作区</Typography.Title>
                <Typography.Text type="secondary">
                  把问题交给 Agent，实时查看推理过程和结果。
                </Typography.Text>
              </div>
              <Button
                className={
                  isInspectorOpen
                    ? "mobile-inspector-toggle"
                    : "inspector-toggle"
                }
                icon={<EyeOutlined />}
                onClick={() =>
                  isInspectorOpen
                    ? setMobileInspectorOpen(true)
                    : setInspectorOpen(true)
                }
              >
                详情
              </Button>
            </div>
            <AgentTimeline run={current} />
            {(current.status === "awaiting_approval" ||
              current.status === "awaiting_clarification") && (
              <Space className="decision-actions">
                {current.status === "awaiting_approval" && (
                  <Button type="primary" onClick={() => void approve()}>
                    确认执行
                  </Button>
                )}
                {current.status === "awaiting_clarification" && (
                  <Button type="primary" onClick={() => void clarify()}>
                    补充为今年各区域
                  </Button>
                )}
              </Space>
            )}
            <Tabs
              className="result-tabs"
              activeKey={activeResultTab}
              onChange={(key) =>
                setActiveResultTab(key as typeof activeResultTab)
              }
              items={resultItems}
            />
            <FeedbackActions />
            <QueryComposer
              status={current.status}
              onSubmit={(question) => void submit(question)}
              onCancel={cancel}
              onRetry={() => void retry()}
            />
          </main>
        </Content>
        {isInspectorOpen && (
          <div className="desktop-inspector">
            <QueryInspector
              run={current}
              onClose={() => setInspectorOpen(false)}
            />
          </div>
        )}
      </Layout>
      <Drawer
        title="查询历史"
        placement="left"
        open={isHistoryOpen}
        onClose={() => setHistoryOpen(false)}
        width={300}
      >
        {historyPanel}
      </Drawer>
      <Drawer
        title="查询详情"
        placement="bottom"
        open={isMobileInspectorOpen}
        onClose={() => setMobileInspectorOpen(false)}
        height="72%"
      >
        <QueryInspector
          run={current}
          onClose={() => setMobileInspectorOpen(false)}
        />
      </Drawer>
    </Layout>
  );
}
