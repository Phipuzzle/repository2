import { create } from "zustand";

import {
  approveQueryRun,
  cancelQueryRun,
  createQueryRun,
  getQueryRun,
  streamQueryEvents,
} from "./api";
import { mockMetricDefinitions } from "./mock";
import type {
  MetricDefinition,
  QueryRun,
  QueryRunStatus,
  SSEEvent,
} from "./types";

interface QueryStore {
  current: QueryRun;
  favoriteIds: string[];
  metrics: MetricDefinition[];
  isInspectorOpen: boolean;
  activeResultTab: "overview" | "chart" | "table" | "sql";
  isHistoryOpen: boolean;
  setActiveResultTab: (tab: QueryStore["activeResultTab"]) => void;
  setInspectorOpen: (open: boolean) => void;
  setHistoryOpen: (open: boolean) => void;
  setMetrics: (metrics: MetricDefinition[]) => void;
  openRun: (id: string) => Promise<void>;
  toggleFavorite: (id: string) => void;
  reset: () => void;
  submit: (question: string) => Promise<void>;
  cancel: () => Promise<void>;
  approve: () => Promise<void>;
  clarify: (clarification: string) => Promise<void>;
  retry: () => Promise<void>;
}

const TERMINAL_STATUSES = new Set<QueryRunStatus>([
  "completed",
  "failed",
  "cancelled",
]);

const HYDRATE_EVENT_TYPES = new Set<SSEEvent["type"]>([
  "sql_generated",
  "sql_validated",
  "sql_authorized",
  "query_started",
  "result_preview",
  "insight_ready",
  "chart_spec_ready",
  "approval_required",
  "approval_granted",
  "clarification_required",
  "run_completed",
  "query_failed",
  "run_failed",
  "run_cancelled",
]);

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

let activeController: AbortController | null = null;
let activeRunId: string | null = null;

function statusForEvent(event: SSEEvent): QueryRunStatus {
  if (event.type === "clarification_required") return "awaiting_clarification";
  if (event.type === "approval_required") return "awaiting_approval";
  if (event.type === "query_failed" || event.type === "run_failed") {
    return "failed";
  }
  if (event.type === "run_cancelled") return "cancelled";
  if (event.type === "run_completed") return "completed";
  return "streaming";
}

function mergeEvents(current: SSEEvent[], incoming: SSEEvent[]): SSEEvent[] {
  const events = new Map(current.map((event) => [event.id, event]));
  for (const event of incoming) events.set(event.id, event);
  return [...events.values()].sort((left, right) => left.id - right.id);
}

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : "查询请求失败，请稍后重试。";
}

function applyRun(current: QueryRun, incoming: QueryRun): QueryRun {
  if (current.id !== incoming.id) return incoming;
  return {
    ...incoming,
    events: mergeEvents(current.events, incoming.events),
    reconnectCount: Math.max(current.reconnectCount, incoming.reconnectCount),
  };
}

export const useQueryStore = create<QueryStore>((set, get) => {
  async function refreshCurrent(runId: string): Promise<void> {
    if (get().current.id !== runId || activeRunId !== runId) return;
    const run = await getQueryRun(runId);
    if (get().current.id !== runId || activeRunId !== runId) return;
    set((state) => ({ current: applyRun(state.current, run) }));
  }

  async function followRun(runId: string): Promise<void> {
    if (activeRunId !== runId || !activeController) return;
    const controller = activeController;
    try {
      await streamQueryEvents(runId, {
        signal: controller.signal,
        lastEventId: get().current.events.at(-1)?.id ?? 0,
        onEvent: async (event) => {
          if (get().current.id !== runId || controller.signal.aborted) return;
          const status = statusForEvent(event);
          const terminal =
            TERMINAL_STATUSES.has(status) ||
            status === "awaiting_approval" ||
            status === "awaiting_clarification";
          set((state) => ({
            current: {
              ...state.current,
              events: mergeEvents(state.current.events, [event]),
              status,
              error:
                event.type === "query_failed" || event.type === "run_failed"
                  ? event.message
                  : state.current.error,
              clarification:
                event.type === "clarification_required"
                  ? event.message
                  : state.current.clarification,
              approvalReason:
                event.type === "approval_required"
                  ? event.message
                  : state.current.approvalReason,
              completedAt: terminal
                ? (state.current.completedAt ?? new Date().toISOString())
                : event.type === "approval_granted"
                  ? null
                  : state.current.completedAt,
            },
          }));
          if (HYDRATE_EVENT_TYPES.has(event.type)) {
            await refreshCurrent(runId);
          }
        },
        onReconnect: (attempt) => {
          if (get().current.id !== runId || controller.signal.aborted) return;
          set((state) => ({
            current: {
              ...state.current,
              reconnectCount: Math.max(state.current.reconnectCount, attempt),
            },
          }));
        },
      });
      await refreshCurrent(runId);
    } catch (error) {
      if (
        controller.signal.aborted ||
        (error instanceof DOMException && error.name === "AbortError")
      ) {
        return;
      }
      set((state) => {
        if (state.current.id !== runId) return state;
        return {
          current: {
            ...state.current,
            status:
              state.current.status === "cancelled"
                ? state.current.status
                : "failed",
            error: describeError(error),
            completedAt:
              state.current.status === "cancelled"
                ? state.current.completedAt
                : new Date().toISOString(),
          },
        };
      });
      try {
        await refreshCurrent(runId);
      } catch {
        // Keep the locally reported connection error when the detail request also fails.
      }
    }
  }

  return {
    current: emptyRun(),
    favoriteIds: [],
    metrics: mockMetricDefinitions(),
    isInspectorOpen: true,
    activeResultTab: "overview",
    isHistoryOpen: false,
    setActiveResultTab: (activeResultTab) => set({ activeResultTab }),
    setInspectorOpen: (isInspectorOpen) => set({ isInspectorOpen }),
    setHistoryOpen: (isHistoryOpen) => set({ isHistoryOpen }),
    setMetrics: (metrics) => set({ metrics }),
    openRun: async (id) => {
      activeController?.abort();
      activeController = null;
      activeRunId = id;
      try {
        const run = await getQueryRun(id);
        set({
          current: run,
          activeResultTab: "overview",
          isHistoryOpen: false,
          isInspectorOpen: true,
        });
        if (run.status === "streaming" || run.status === "submitting") {
          activeController = new AbortController();
          void followRun(id);
        }
      } catch (error) {
        set((state) => ({
          current: {
            ...state.current,
            status: "failed",
            error: describeError(error),
          },
        }));
      }
    },
    toggleFavorite: (id) =>
      set((state) => ({
        favoriteIds: state.favoriteIds.includes(id)
          ? state.favoriteIds.filter((favoriteId) => favoriteId !== id)
          : [...state.favoriteIds, id],
      })),
    reset: () => {
      activeController?.abort();
      activeController = null;
      activeRunId = null;
      set({ current: emptyRun(), activeResultTab: "overview" });
    },
    cancel: async () => {
      const run = get().current;
      if (!run.id || run.id === "new" || TERMINAL_STATUSES.has(run.status)) {
        return;
      }
      try {
        const cancelled = await cancelQueryRun(run.id);
        set((state) => ({ current: applyRun(state.current, cancelled) }));
        activeController?.abort();
        activeController = null;
        activeRunId = null;
      } catch (error) {
        set((state) => ({
          current: {
            ...state.current,
            error: describeError(error),
          },
        }));
      }
    },
    approve: async () => {
      const current = get().current;
      if (current.id === "new" || current.status !== "awaiting_approval")
        return;
      try {
        const approved = await approveQueryRun(current.id);
        set((state) => ({ current: applyRun(state.current, approved) }));
        activeController?.abort();
        activeController = new AbortController();
        activeRunId = approved.id;
        await followRun(approved.id);
      } catch (error) {
        set((state) => ({
          current: {
            ...state.current,
            error: describeError(error),
          },
        }));
      }
    },
    clarify: async (clarification) => {
      const question = get().current.question;
      const value = clarification.trim();
      if (!value) return;
      await get().submit(`${question}。补充条件：${value}`);
    },
    retry: async () => {
      const question = get().current.question;
      if (question) await get().submit(question);
    },
    submit: async (question) => {
      activeController?.abort();
      activeController = new AbortController();
      const controller = activeController;
      activeRunId = null;
      set({
        current: {
          ...emptyRun(),
          question,
          status: "submitting",
          startedAt: new Date().toISOString(),
        },
        activeResultTab: "overview",
      });
      try {
        const run = await createQueryRun(question, controller.signal);
        if (controller.signal.aborted) return;
        activeRunId = run.id;
        set({
          current: run,
          activeResultTab: "overview",
          isInspectorOpen: true,
        });
        await followRun(run.id);
      } catch (error) {
        if (
          controller.signal.aborted ||
          (error instanceof DOMException && error.name === "AbortError")
        ) {
          return;
        }
        set((state) => ({
          current: {
            ...state.current,
            status: "failed",
            error: describeError(error),
            completedAt: new Date().toISOString(),
          },
        }));
      }
    },
  };
});
