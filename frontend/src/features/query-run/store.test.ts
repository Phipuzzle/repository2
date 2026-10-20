import { act } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useQueryStore } from "./store";

describe("query run mock workflow", () => {
  beforeEach(() => {
    useQueryStore.getState().reset();
    useQueryStore.getState().clearHistory();
  });

  it("streams a completed query into result and chart state", async () => {
    await act(async () =>
      useQueryStore.getState().submit("查询今年销售额趋势"),
    );
    const run = useQueryStore.getState().current;
    expect(run.status).toBe("completed");
    expect(run.events.map((event) => event.type)).toContain("chart_spec_ready");
    expect(run.result?.rows.length).toBeGreaterThan(0);
    expect(run.chartSpec?.type).toBe("line");
    expect(useQueryStore.getState().history).toHaveLength(1);
    useQueryStore.getState().setActiveResultTab("sql");
    useQueryStore.getState().selectHistory(run.id);
    expect(useQueryStore.getState().current.id).toBe(run.id);
    expect(useQueryStore.getState().activeResultTab).toBe("overview");
    useQueryStore.getState().clearHistory();
    expect(useQueryStore.getState().history).toHaveLength(0);
  });

  it("exposes approval and failure states from natural-language mock modes", async () => {
    await act(async () => useQueryStore.getState().submit("成本确认查询"));
    expect(useQueryStore.getState().current.status).toBe("awaiting_approval");
    await act(async () => useQueryStore.getState().submit("模拟失败查询"));
    expect(useQueryStore.getState().current.status).toBe("failed");
  });

  it("preserves cancellation and clarification as actionable terminal states", async () => {
    const pending = useQueryStore.getState().submit("查询取消场景");
    await new Promise((resolve) => setTimeout(resolve, 300));
    useQueryStore.getState().cancel();
    await act(async () => pending);
    expect(useQueryStore.getState().current.status).toBe("cancelled");

    await act(async () =>
      useQueryStore.getState().submit("需要补充条件的查询"),
    );
    expect(useQueryStore.getState().current.status).toBe(
      "awaiting_clarification",
    );
  });

  it("does not let an older stream overwrite a newer query", async () => {
    const olderRun = useQueryStore.getState().submit("旧查询任务");
    await new Promise((resolve) => setTimeout(resolve, 300));
    await act(async () => useQueryStore.getState().submit("新查询任务"));
    await act(async () => olderRun);
    expect(useQueryStore.getState().current.question).toBe("新查询任务");
    expect(useQueryStore.getState().current.status).toBe("completed");
  });
});
