import { create } from "zustand";

import {
  mockChartSpec,
  mockMetricDefinitions,
  mockQueryResult,
  mockQueryRun,
  mockSql,
} from "./mock";
import type {
  MetricDefinition,
  QueryHistoryItem,
  QueryRun,
  QueryRunStatus,
  SSEEvent,
} from "./types";

interface QueryStore {
  current: QueryRun;
  history: QueryHistoryItem[];
  historyRuns: Record<string, QueryRun>;
  favoriteIds: string[];
  metrics: MetricDefinition[];
  isInspectorOpen: boolean;
  activeResultTab: "overview" | "chart" | "table" | "sql";
  isHistoryOpen: boolean;
  setActiveResultTab: (tab: QueryStore["activeResultTab"]) => void;
  setInspectorOpen: (open: boolean) => void;
  setHistoryOpen: (open: boolean) => void;
  selectHistory: (id: string) => void;
  clearHistory: () => void;
  toggleFavorite: (id: string) => void;
  reset: () => void;
  submit: (question: string) => Promise<void>;
  cancel: () => void;
  approve: () => Promise<void>;
  clarify: () => Promise<void>;
  retry: () => Promise<void>;
}

const emptyRun = (): QueryRun => ({
  id: "new",
  question: "",
  status: "idle",
  events: [],
  sql: "",
  result: null,
  chartSpec: null,
  insight: "",
  error: null,
  clarification: null,
  approvalReason: null,
  reconnectCount: 0,
  startedAt: null,
  completedAt: null,
});

let runSequence = 0;

function statusForEvent(event: SSEEvent): QueryRunStatus {
  if (event.type === "clarification_required") return "awaiting_clarification";
  if (event.type === "approval_required") return "awaiting_approval";
  if (event.type === "query_failed") return "failed";
  if (event.type === "run_cancelled") return "cancelled";
  if (event.type === "run_completed") return "completed";
  return "streaming";
}

export const useQueryStore = create<QueryStore>((set, get) => ({
  current: emptyRun(),
  history: [],
  historyRuns: {},
  favoriteIds: [],
  metrics: mockMetricDefinitions(),
  isInspectorOpen: true,
  activeResultTab: "overview",
  isHistoryOpen: false,
  setActiveResultTab: (activeResultTab) => set({ activeResultTab }),
  setInspectorOpen: (isInspectorOpen) => set({ isInspectorOpen }),
  setHistoryOpen: (isHistoryOpen) => set({ isHistoryOpen }),
  selectHistory: (id) => {
    const run = get().historyRuns[id];
    if (run)
      set({ current: run, activeResultTab: "overview", isHistoryOpen: false });
  },
  clearHistory: () => set({ history: [], historyRuns: {}, favoriteIds: [] }),
  toggleFavorite: (id) =>
    set((state) => ({
      favoriteIds: state.favoriteIds.includes(id)
        ? state.favoriteIds.filter((favoriteId) => favoriteId !== id)
        : [...state.favoriteIds, id],
    })),
  reset: () => set({ current: emptyRun(), activeResultTab: "overview" }),
  cancel: () =>
    set((state) => ({
      current: {
        ...state.current,
        status: "cancelled",
        error: "查询已由用户取消",
      },
    })),
  approve: async () => {
    const question = get().current.question;
    await get().submit(`${question} 已确认执行`);
  },
  clarify: async () => {
    const question = get().current.question;
    await get().submit(`${question} 已补充条件：今年，按区域统计`);
  },
  retry: async () => {
    const question = get().current.question;
    if (question) await get().submit(question);
  },
  submit: async (question) => {
    const runId = `run-${Date.now()}-${++runSequence}`;
    const startedAt = new Date().toISOString();
    set({
      current: {
        ...emptyRun(),
        id: runId,
        question,
        status: "submitting",
        startedAt,
      },
      activeResultTab: "overview",
    });
    await mockQueryRun(question, (event) => {
      const current = get().current;
      if (current.id !== runId || current.status === "cancelled") return;
      const events = [...current.events, event];
      const status = statusForEvent(event);
      const isReconnect = event.type === "reconnected";
      const next: QueryRun = {
        ...current,
        events,
        status,
        reconnectCount: current.reconnectCount + (isReconnect ? 1 : 0),
        sql: event.type === "sql_generated" ? mockSql(question) : current.sql,
        result:
          event.type === "result_preview"
            ? mockQueryResult(
                question.includes("空结果"),
                question.includes("权限"),
              )
            : current.result,
        chartSpec:
          event.type === "chart_spec_ready"
            ? mockChartSpec(current.result ?? mockQueryResult())
            : current.chartSpec,
        insight:
          event.type === "run_completed"
            ? "今年以来华东区域销售额持续增长，6 月达到阶段最高值，较 1 月提升约 59%。"
            : current.insight,
        error: event.type === "query_failed" ? event.message : current.error,
        clarification:
          event.type === "clarification_required"
            ? event.message
            : current.clarification,
        approvalReason:
          event.type === "approval_required"
            ? event.message
            : current.approvalReason,
        completedAt: [
          "run_completed",
          "query_failed",
          "run_cancelled",
          "clarification_required",
          "approval_required",
        ].includes(event.type)
          ? new Date().toISOString()
          : current.completedAt,
      };
      set({ current: next });
    });
    const finished = get().current;
    if (finished.id === runId && finished.status !== "streaming") {
      set((state) => ({
        history: [
          {
            id: finished.id,
            question: finished.question,
            status: finished.status,
            createdAt: startedAt,
            durationMs: 1800,
          },
          ...state.history,
        ].slice(0, 20),
        historyRuns: { ...state.historyRuns, [finished.id]: finished },
      }));
    }
  },
}));
