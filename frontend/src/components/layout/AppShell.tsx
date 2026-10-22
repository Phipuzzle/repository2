"use client";

import { useEffect, useRef, useState } from "react";
import { Alert, Button, Drawer, Layout, Space, Tabs, Typography } from "antd";
import { EyeOutlined } from "@ant-design/icons";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { getAuthSession, signOut } from "../../features/auth/oidc";
import {
  getMetrics,
  listQueryRuns,
  toHistoryItem,
} from "../../features/query-run/api";
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

function Workspace() {
  const queryClient = useQueryClient();
  const [isMobileInspectorOpen, setMobileInspectorOpen] = useState(false);
  const initializedHistory = useRef(false);
  const {
    current,
    favoriteIds,
    metrics,
    activeResultTab,
    isInspectorOpen,
    isHistoryOpen,
    setActiveResultTab,
    setInspectorOpen,
    setHistoryOpen,
    setMetrics,
    openRun,
    toggleFavorite,
    reset,
    submit,
    cancel,
    retry,
    approve,
    recompute,
    clarify,
  } = useQueryStore();

  const historyQuery = useQuery({
    queryKey: ["query-runs"],
    queryFn: ({ signal }) => listQueryRuns(20, 0, signal),
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
  const metricsQuery = useQuery({
    queryKey: ["metrics"],
    queryFn: ({ signal }) => getMetrics(signal),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (!historyQuery.data) return;
    const known = new Set(historyQuery.data.items.map((run) => run.id));
    if (!initializedHistory.current && historyQuery.data.items[0]) {
      initializedHistory.current = true;
      void openRun(historyQuery.data.items[0].id);
    } else if (!initializedHistory.current) {
      initializedHistory.current = true;
    }
    if (
      current.id !== "new" &&
      !known.has(current.id) &&
      !["submitting", "streaming"].includes(current.status)
    ) {
      void queryClient.invalidateQueries({ queryKey: ["query-runs"] });
    }
  }, [current.id, current.status, historyQuery.data, openRun, queryClient]);

  useEffect(() => {
    if (
      [
        "completed",
        "failed",
        "cancelled",
        "awaiting_approval",
        "awaiting_clarification",
      ].includes(current.status)
    ) {
      void queryClient.invalidateQueries({ queryKey: ["query-runs"] });
    }
  }, [current.id, current.status, queryClient]);

  useEffect(() => {
    if (metricsQuery.data) setMetrics(metricsQuery.data);
  }, [metricsQuery.data, setMetrics]);

  const history = historyQuery.data?.items.map(toHistoryItem) ?? [];
  const resultItems = [
    {
      key: "overview",
      label: "概览",
      children: <InsightSummary run={current} />,
    },
    {
      key: "chart",
      label: "图表",
      children: (
        <ChartPanel
          spec={current.chartSpec}
          emptyResult={
            current.status === "completed" && current.result?.total === 0
          }
        />
      ),
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
      isLoading={historyQuery.isLoading}
      onSelect={(item) => void openRun(item.id)}
      onToggleFavorite={toggleFavorite}
    />
  );
  const requestError =
    historyQuery.error instanceof Error
      ? historyQuery.error.message
      : metricsQuery.error instanceof Error
        ? metricsQuery.error.message
        : current.error &&
            current.status === "failed" &&
            current.events.length === 0
          ? current.error
          : null;

  return (
    <Layout className="app-layout">
      <AppHeader
        userLabel={getAuthSession()?.username ?? "已登录用户"}
        onNew={reset}
        onHistory={() => setHistoryOpen(true)}
        onSignOut={signOut}
      />
      <Layout>
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
            {requestError && (
              <Alert
                className="workspace-error"
                type="error"
                showIcon
                message={requestError}
              />
            )}
            <AgentTimeline run={current} />
            {current.status === "awaiting_approval" && (
              <Space className="decision-actions">
                <Button type="primary" onClick={() => void approve()}>
                  确认执行
                </Button>
              </Space>
            )}
            {current.status === "awaiting_clarification" && (
              <Alert
                className="workspace-error"
                type="warning"
                showIcon
                message="请在下方输入补充条件后提交。"
              />
            )}
            <Tabs
              className="result-tabs"
              activeKey={activeResultTab}
              onChange={(key) =>
                setActiveResultTab(key as typeof activeResultTab)
              }
              items={resultItems}
            />
            <FeedbackActions runId={current.id === "new" ? null : current.id} />
            <QueryComposer
              status={current.status}
              onCancel={() => void cancel()}
              onRecompute={() => void recompute()}
              onSubmit={(question) =>
                void (current.status === "awaiting_clarification"
                  ? clarify(question)
                  : submit(
                      question,
                      current.status === "completed"
                        ? current.conversationId
                        : null,
                    ))
              }
              onRetry={() => void retry()}
            />
          </main>
        </Content>
        {isInspectorOpen && (
          <div className="desktop-inspector">
            <QueryInspector
              run={current}
              metrics={metrics}
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
          metrics={metrics}
          onClose={() => setMobileInspectorOpen(false)}
        />
      </Drawer>
    </Layout>
  );
}

export function AppShell() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
          },
          mutations: { retry: 0 },
        },
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <Workspace />
    </QueryClientProvider>
  );
}
