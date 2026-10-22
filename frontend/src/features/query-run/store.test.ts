import { act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { QueryRun, SSEEvent } from "./types";

const apiState = vi.hoisted(() => ({
  sequence: 0,
  runs: new Map<string, QueryRun>(),
  approved: new Set<string>(),
}));

vi.mock("./api", () => {
  const baseRun = (id: string, question: string): QueryRun => ({
    id,
    question,
    status: "submitting",
    events: [],
    sql: "",
    result: null,
    chartSpec: null,
    insight: "",
    error: null,
    clarification: null,
    approvalReason: null,
    reconnectCount: 0,
    conversationId: null,
    turnIndex: 0,
    startedAt: new Date().toISOString(),
    completedAt: null,
  });
  let eventSequence = 0;
  const event = (
    type: SSEEvent["type"],
    message: string,
    data?: SSEEvent["data"],
  ): SSEEvent => ({
    id: ++eventSequence,
    type,
    message,
    data,
    timestamp: new Date().toISOString(),
  });
  const save = (run: QueryRun) => {
    apiState.runs.set(run.id, run);
    return structuredClone(run);
  };
  const emit = async (
    run: QueryRun,
    options: {
      onEvent: (event: SSEEvent) => void | Promise<void>;
    },
    next: SSEEvent,
  ) => {
    run.events.push(next);
    save(run);
    await options.onEvent(next);
  };
  const complete = async (
    run: QueryRun,
    options: { onEvent: (event: SSEEvent) => void | Promise<void> },
  ) => {
    await emit(run, options, event("sql_generated", "已生成 SQL"));
    run.sql = "SELECT month, sales FROM analytics.demo_orders";
    run.status = "streaming";
    save(run);
    await emit(run, options, event("result_preview", "已返回结果"));
    run.result = {
      rows: [
        { month: "2026-01", sales: 128000 },
        { month: "2026-02", sales: 146500 },
      ],
      schema: [
        { name: "month", type: "string", label: "月份" },
        { name: "sales", type: "number", label: "销售额" },
      ],
      total: 2,
    };
    save(run);
    await emit(run, options, event("chart_spec_ready", "已生成图表"));
    run.chartSpec = {
      type: "line",
      title: "月销售额趋势",
      xField: "month",
      yField: "sales",
      dataset: run.result.rows.map((row) => ({
        month: String(row.month),
        sales: Number(row.sales),
      })),
    };
    run.insight = "销售额保持增长。";
    save(run);
    await emit(run, options, event("run_completed", "查询完成"));
    run.status = "completed";
    run.completedAt = new Date().toISOString();
    save(run);
  };

  return {
    createQueryRun: vi.fn(async (question: string) => {
      const run = baseRun(`run-${++apiState.sequence}`, question);
      return save(run);
    }),
    getQueryRun: vi.fn(async (runId: string) => {
      const run = apiState.runs.get(runId);
      if (!run) throw new Error("Query run not found");
      return structuredClone(run);
    }),
    cancelQueryRun: vi.fn(async (runId: string) => {
      const run = apiState.runs.get(runId);
      if (!run) throw new Error("Query run not found");
      run.status = "cancelled";
      run.completedAt = new Date().toISOString();
      return save(run);
    }),
    approveQueryRun: vi.fn(async (runId: string) => {
      const run = apiState.runs.get(runId);
      if (!run) throw new Error("Query run not found");
      apiState.approved.add(runId);
      run.status = "streaming";
      return save(run);
    }),
    streamQueryEvents: vi.fn(
      async (
        runId: string,
        options: {
          signal: AbortSignal;
          onEvent: (event: SSEEvent) => void | Promise<void>;
          onReconnect?: (attempt: number) => void;
        },
      ) => {
        const run = apiState.runs.get(runId);
        if (!run) throw new Error("Query run not found");
        const question = run.question;
        if (question.includes("重连")) options.onReconnect?.(1);
        if (question.includes("取消")) {
          await new Promise<void>((_, reject) => {
            options.signal.addEventListener(
              "abort",
              () => reject(new DOMException("Aborted", "AbortError")),
              { once: true },
            );
          });
          return;
        }
        if (question.includes("旧查询")) {
          await new Promise((resolve) => setTimeout(resolve, 80));
        }
        if (question.includes("失败")) {
          run.status = "failed";
          run.error = "SQL 权限校验失败";
          save(run);
          await emit(run, options, event("run_failed", run.error));
          return;
        }
        if (question.includes("成本确认") && !apiState.approved.has(runId)) {
          run.status = "awaiting_approval";
          run.approvalReason = "查询成本较高";
          save(run);
          await emit(
            run,
            options,
            event("approval_required", run.approvalReason),
          );
          return;
        }
        await complete(run, options);
      },
    ),
    ApiError: class ApiError extends Error {},
  };
});

import { useQueryStore } from "./store";

describe("query run API workflow", () => {
  beforeEach(() => {
    useQueryStore.getState().reset();
    apiState.runs.clear();
    apiState.approved.clear();
    apiState.sequence = 0;
  });

  it("streams a real query into SQL, result and chart state", async () => {
    await act(async () =>
      useQueryStore.getState().submit("查询今年销售额趋势"),
    );
    const run = useQueryStore.getState().current;
    expect(run.status).toBe("completed");
    expect(run.events.map((item) => item.type)).toContain("chart_spec_ready");
    expect(run.result?.rows).toHaveLength(2);
    expect(run.chartSpec?.type).toBe("line");
    expect(run.sql).toContain("SELECT");
  });

  it("connects approval and resume to the real query actions", async () => {
    await act(async () =>
      useQueryStore.getState().submit("需要成本确认的查询"),
    );
    expect(useQueryStore.getState().current.status).toBe("awaiting_approval");
    await act(async () => useQueryStore.getState().approve());
    expect(useQueryStore.getState().current.status).toBe("completed");
  });

  it("keeps failed, cancelled, clarification and reconnect states actionable", async () => {
    await act(async () => useQueryStore.getState().submit("模拟失败查询"));
    expect(useQueryStore.getState().current.status).toBe("failed");
    expect(useQueryStore.getState().current.error).toContain("权限");

    const pending = useQueryStore.getState().submit("查询取消场景");
    await Promise.resolve();
    await act(async () => useQueryStore.getState().cancel());
    await act(async () => pending);
    expect(useQueryStore.getState().current.status).toBe("cancelled");

    await act(async () => useQueryStore.getState().submit("断线重连查询"));
    expect(useQueryStore.getState().current.reconnectCount).toBe(1);
  });

  it("does not let an older stream overwrite a newer query", async () => {
    const olderRun = useQueryStore.getState().submit("旧查询任务");
    await Promise.resolve();
    await act(async () => useQueryStore.getState().submit("新查询任务"));
    await act(async () => olderRun);
    expect(useQueryStore.getState().current.question).toBe("新查询任务");
    expect(useQueryStore.getState().current.status).toBe("completed");
  });
});
