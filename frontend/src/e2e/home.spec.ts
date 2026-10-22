import { expect, test, type Page, type Route } from "@playwright/test";
import type { QueryRun, SSEEvent } from "../features/query-run/types";

const API_ORIGIN = "http://localhost:8000";
const RUN_ID = "0f79a2c2-fa44-4fe1-978a-cc10600da200";
const CONVERSATION_ID = "9e1f4b6e-8d2a-4c57-b3b0-6f5a2d7c8e19";

type Scenario =
  | "success"
  | "approval"
  | "cancel"
  | "reconnect"
  | "failure"
  | "empty"
  | "followup";

function event(id: number, type: SSEEvent["type"], message: string): SSEEvent {
  return {
    id,
    type,
    message,
    timestamp: new Date(Date.UTC(2026, 9, 22, 10, 0, id)).toISOString(),
  };
}

function baseRun(question: string): QueryRun {
  return {
    id: RUN_ID,
    question,
    status: "submitting",
    events: [event(1, "submitted", "已提交查询")],
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
    startedAt: "2026-10-22T10:00:00Z",
    completedAt: null,
  };
}

function completedRun(run: QueryRun): QueryRun {
  return {
    ...run,
    status: "completed",
    sql: "SELECT month, sales FROM analytics.demo_orders",
    result: {
      rows: [
        { month: "2026-01", region: "华东", sales: 128000 },
        { month: "2026-02", region: "华东", sales: 146500 },
      ],
      schema: [
        { name: "month", type: "string", label: "月份" },
        { name: "region", type: "string", label: "区域" },
        { name: "sales", type: "number", label: "销售额" },
      ],
      total: 2,
    },
    chartSpec: {
      type: "line",
      title: "华东区域月销售额趋势",
      xField: "month",
      yField: "sales",
      dataset: [
        { month: "2026-01", sales: 128000 },
        { month: "2026-02", sales: 146500 },
      ],
    },
    insight: "华东区域销售额保持增长，2 月较 1 月继续提升。",
    completedAt: "2026-10-22T10:00:04Z",
  };
}

function emptyRun(run: QueryRun): QueryRun {
  return {
    ...run,
    status: "completed",
    sql: "SELECT month, sales FROM analytics.demo_orders WHERE false",
    result: {
      rows: [],
      schema: [
        { name: "month", type: "string", label: "月份" },
        { name: "sales", type: "number", label: "销售额" },
      ],
      total: 0,
    },
    chartSpec: null,
    insight: "查询成功，但没有匹配的数据。",
    completedAt: "2026-10-22T10:00:04Z",
  };
}

function sseBody(events: SSEEvent[], includeEnd = true): string {
  const frames = events.map(
    (item) =>
      `id: ${item.id}\nevent: ${item.type}\ndata: ${JSON.stringify(item)}\n\n`,
  );
  if (includeEnd) frames.push("event: stream_end\ndata: {}\n\n");
  return frames.join("");
}

async function cors(
  route: Route,
  body = "",
  status = 200,
  contentType = "application/json",
) {
  await route.fulfill({
    status,
    body,
    contentType,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers":
        "Authorization, Content-Type, Accept, Last-Event-ID",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    },
  });
}

async function prepareWorkspace(page: Page, scenario: Scenario) {
  await page.addInitScript(() => {
    sessionStorage.setItem(
      "ida.oidc.session",
      JSON.stringify({
        accessToken: "playwright-token",
        refreshToken: null,
        idToken: null,
        expiresAt: Date.now() + 3_600_000,
        username: "e2e-developer",
      }),
    );
  });

  let run = baseRun("");
  let created = false;
  let approved = false;
  let reconnectCalls = 0;
  let completed = false;
  let capturedFollowUpConversationId: string | null = null;

  await page.route(`${API_ORIGIN}/api/v1/**`, async (route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") {
      await cors(route, "", 204);
      return;
    }
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    if (request.method() === "GET" && path === "/metrics") {
      await cors(
        route,
        JSON.stringify([
          {
            name: "销售额",
            definition: "有效订单实付金额之和。",
            source: "analytics.demo_orders.total_amount",
            updatedAt: "2026-10-22T10:00:00Z",
          },
        ]),
      );
      return;
    }
    if (request.method() === "GET" && path === "/query-runs") {
      await cors(
        route,
        JSON.stringify({
          items: created ? [run] : [],
          total: created ? 1 : 0,
          limit: 20,
          offset: 0,
        }),
      );
      return;
    }
    if (request.method() === "POST" && path === "/query-runs") {
      const payload = request.postDataJSON() as {
        question: string;
        conversation_id?: string | null;
      };
      const isFollowUp = created;
      run = baseRun(payload.question);
      created = true;
      completed = false;
      approved = false;
      reconnectCalls = 0;
      if (scenario === "followup") {
        run.conversationId = CONVERSATION_ID;
        run.turnIndex = isFollowUp ? 1 : 0;
        if (isFollowUp) {
          capturedFollowUpConversationId = payload.conversation_id ?? null;
        }
      }
      await cors(route, JSON.stringify(run), 201);
      return;
    }
    if (path === `/query-runs/${RUN_ID}/events`) {
      if (scenario === "failure") {
        const failure = event(
          2,
          "run_failed",
          "当前账号无权访问请求的敏感字段",
        );
        run.events = [...run.events, failure];
        run.status = "failed";
        run.error = failure.message;
        run.completedAt = "2026-10-22T10:00:02Z";
        await cors(route, sseBody([failure]), 200, "text/event-stream");
        return;
      }
      if (scenario === "empty") {
        const streamed = [
          event(2, "sql_generated", "已生成 SQL"),
          event(3, "run_completed", "查询完成"),
        ];
        run = emptyRun({ ...run, events: [...run.events, ...streamed] });
        await cors(route, sseBody(streamed), 200, "text/event-stream");
        return;
      }
      if (scenario === "reconnect") {
        reconnectCalls += 1;
        if (reconnectCalls === 1) {
          const sqlEvent = event(2, "sql_generated", "已生成 SQL");
          run.events = [run.events[0], sqlEvent];
          run.status = "streaming";
          await cors(
            route,
            sseBody([sqlEvent], false),
            200,
            "text/event-stream",
          );
          return;
        }
        const resumed = [
          event(3, "chart_spec_ready", "已生成图表"),
          event(4, "run_completed", "查询完成"),
        ];
        run = completedRun({
          ...run,
          events: [...run.events, ...resumed],
          reconnectCount: 1,
        });
        completed = true;
        await cors(route, sseBody(resumed), 200, "text/event-stream");
        return;
      }
      if (scenario === "approval" && !approved) {
        const approval = event(
          2,
          "approval_required",
          "查询预计扫描较多数据，需要确认",
        );
        run.events = [...run.events, approval];
        run.status = "awaiting_approval";
        run.approvalReason = approval.message;
        await cors(route, sseBody([approval]), 200, "text/event-stream");
        return;
      }
      if (scenario === "cancel" && !completed) {
        const started = event(2, "query_started", "正在查询 PostgreSQL");
        run.events = [...run.events, started];
        run.status = "streaming";
        await cors(route, sseBody([started]), 200, "text/event-stream");
        return;
      }
      const nextId = approved ? 4 : 2;
      const streamed = [
        event(nextId, "sql_generated", "已生成 SQL"),
        event(nextId + 1, "chart_spec_ready", "已生成图表"),
        event(nextId + 2, "run_completed", "查询完成"),
      ];
      run = completedRun({ ...run, events: [...run.events, ...streamed] });
      completed = true;
      await cors(route, sseBody(streamed), 200, "text/event-stream");
      return;
    }
    if (
      request.method() === "POST" &&
      path === `/query-runs/${RUN_ID}/approve`
    ) {
      approved = true;
      run = {
        ...run,
        status: "streaming",
        events: [...run.events, event(3, "approval_granted", "已确认执行")],
      };
      await cors(route, JSON.stringify(run));
      return;
    }
    if (
      request.method() === "POST" &&
      path === `/query-runs/${RUN_ID}/cancel`
    ) {
      run = {
        ...run,
        status: "cancelled",
        events: [...run.events, event(3, "run_cancelled", "查询已取消")],
        completedAt: "2026-10-22T10:00:03Z",
      };
      await cors(route, JSON.stringify(run));
      return;
    }
    if (request.method() === "POST" && path === "/feedback") {
      await cors(
        route,
        JSON.stringify({
          id: RUN_ID,
          run_id: RUN_ID,
          rating: "positive",
          comment: null,
          created_at: "2026-10-22T10:00:05Z",
        }),
        201,
      );
      return;
    }
    if (request.method() === "GET" && path === `/query-runs/${RUN_ID}`) {
      await cors(route, JSON.stringify(run));
      return;
    }
    await cors(
      route,
      JSON.stringify({ detail: { message: `Unhandled ${path}` } }),
      404,
    );
  });

  return {
    getConversationId: () => capturedFollowUpConversationId,
  };
}

async function ask(page: Page, question: string) {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "数据分析工作区" }),
  ).toBeVisible();
  await page.getByPlaceholder("用自然语言描述你想了解的数据...").fill(question);
  await page.getByRole("button", { name: "开始分析" }).click();
}

test("renders timeline, SQL, result table, ChartSpec and feedback", async ({
  page,
}) => {
  await prepareWorkspace(page, "success");
  await ask(page, "查询今年各区域月销售额并生成趋势图");

  await expect(
    page.getByText("执行链路已完成", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("华东区域销售额保持增长", { exact: false }),
  ).toBeVisible();

  await page.getByRole("tab", { name: "图表" }).click();
  await expect(page.getByText("华东区域月销售额趋势")).toBeVisible();
  await expect(page.locator(".chart-canvas canvas")).toBeVisible();

  await page.getByRole("tab", { name: "数据表" }).click();
  await expect(
    page.getByRole("columnheader", { name: "销售额" }),
  ).toBeVisible();
  await expect(page.getByText("146,500")).toBeVisible();

  await page.getByRole("tab", { name: "SQL" }).click();
  await expect(
    page.getByText("SELECT month, sales", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "结果正确" }).click();
  await expect(page.getByText("感谢你的反馈")).toBeVisible();
});

test("approves a high-cost query and resumes the SSE stream", async ({
  page,
}) => {
  await prepareWorkspace(page, "approval");
  await ask(page, "统计全年订单明细并确认成本");
  await expect(
    page.getByText("查询预计扫描较多数据，需要确认", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "确认执行" }).click();
  await expect(page.getByText("已确认执行", { exact: false })).toBeVisible();
  await expect(
    page.getByText("执行链路已完成", { exact: false }),
  ).toBeVisible();
});

test("cancels a running query through the query action API", async ({
  page,
}) => {
  await prepareWorkspace(page, "cancel");
  await ask(page, "取消这个慢查询");
  await expect(page.getByRole("button", { name: "取消查询" })).toBeVisible();
  await page.getByRole("button", { name: "取消查询" }).click();
  await expect(page.getByText("已取消", { exact: true }).first()).toBeVisible();
});

test("reconnects after an interrupted SSE response and resumes from the cursor", async ({
  page,
}) => {
  await prepareWorkspace(page, "reconnect");
  await ask(page, "验证断线重连");
  await expect(page.getByText("已重连 1 次")).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByText("执行链路已完成", { exact: false }),
  ).toBeVisible();
});

test("shows permission failures with a retry action", async ({ page }) => {
  await prepareWorkspace(page, "failure");
  await ask(page, "查询无权限字段");
  await expect(
    page.getByText("当前账号无权访问请求的敏感字段", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "重试" })).toBeVisible();
});

test("renders a successful empty result without a chart", async ({ page }) => {
  await prepareWorkspace(page, "empty");
  await ask(page, "查询不存在的数据");
  await expect(
    page.getByText("查询成功，但没有匹配的数据。", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "图表" }).click();
  await expect(page.getByText("没有可视化数据")).toBeVisible();
  await page.getByRole("tab", { name: "数据表" }).click();
  await expect(page.getByText("没有匹配的数据", { exact: true })).toBeVisible();
});

test("chains a follow-up question in the same conversation", async ({
  page,
}) => {
  const state = await prepareWorkspace(page, "followup");
  await ask(page, "查询今年各区域销售额");
  await expect(
    page.getByText("执行链路已完成", { exact: false }),
  ).toBeVisible();

  await page
    .getByPlaceholder("用自然语言描述你想了解的数据...")
    .fill("只看华东");
  await page.getByRole("button", { name: "开始分析" }).click();
  await expect(
    page.getByText("执行链路已完成", { exact: false }),
  ).toBeVisible();

  expect(state.getConversationId()).toBe(CONVERSATION_ID);
});
