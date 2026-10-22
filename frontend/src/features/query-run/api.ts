import { AuthenticationRequiredError, getAccessToken } from "../auth/oidc";
import { parseEventPayload, readSSEFrames } from "./sse";
import type {
  MetricDefinition,
  QueryHistoryItem,
  QueryResult,
  QueryRun,
  QueryRunList,
  SSEEvent,
} from "./types";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");

export interface StreamOptions {
  signal: AbortSignal;
  lastEventId?: number;
  onEvent: (event: SSEEvent) => void | Promise<void>;
  onReconnect?: (attempt: number) => void;
  reconnectDelayMs?: number;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function errorMessage(value: unknown, fallback: string): string {
  if (
    value &&
    typeof value === "object" &&
    "detail" in value &&
    typeof value.detail === "object" &&
    value.detail !== null
  ) {
    const detail = value.detail as { message?: unknown; code?: unknown };
    return typeof detail.message === "string" ? detail.message : fallback;
  }
  return fallback;
}

function errorCode(value: unknown): string | undefined {
  if (
    value &&
    typeof value === "object" &&
    "detail" in value &&
    typeof value.detail === "object" &&
    value.detail !== null &&
    "code" in value.detail &&
    typeof value.detail.code === "string"
  ) {
    return value.detail.code;
  }
  return undefined;
}

async function apiFetch(
  path: string,
  init: RequestInit = {},
  retryAuth = true,
): Promise<Response> {
  const token = await getAccessToken();
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  headers.set("Accept", "application/json");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });
  if (response.status === 401 && retryAuth) {
    const refreshed = await getAccessToken(true);
    const retryHeaders = new Headers(headers);
    retryHeaders.set("Authorization", `Bearer ${refreshed}`);
    return fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: retryHeaders,
    });
  }
  return response;
}

async function jsonRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await apiFetch(path, init);
  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new ApiError(
      errorMessage(payload, `API request failed (${response.status})`),
      response.status,
      errorCode(payload),
    );
  }
  return (await response.json()) as T;
}

export async function createQueryRun(
  question: string,
  conversationId?: string | null,
  signal?: AbortSignal,
): Promise<QueryRun> {
  return jsonRequest<QueryRun>("/query-runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      conversation_id: conversationId ?? null,
    }),
    signal,
  });
}

export async function getQueryRun(
  runId: string,
  signal?: AbortSignal,
): Promise<QueryRun> {
  return jsonRequest<QueryRun>(`/query-runs/${encodeURIComponent(runId)}`, {
    signal,
  });
}

export async function listQueryRuns(
  limit = 20,
  offset = 0,
  signal?: AbortSignal,
): Promise<QueryRunList> {
  return jsonRequest<QueryRunList>(
    `/query-runs?limit=${limit}&offset=${offset}`,
    { signal },
  );
}

export async function getQueryResult(
  runId: string,
  limit = 100,
  offset = 0,
  signal?: AbortSignal,
): Promise<QueryResult> {
  return jsonRequest<QueryResult>(
    `/query-runs/${encodeURIComponent(runId)}/result?limit=${limit}&offset=${offset}`,
    { signal },
  );
}

export async function getMetrics(
  signal?: AbortSignal,
): Promise<MetricDefinition[]> {
  return jsonRequest<MetricDefinition[]>("/metrics", { signal });
}

export async function cancelQueryRun(runId: string): Promise<QueryRun> {
  return jsonRequest<QueryRun>(
    `/query-runs/${encodeURIComponent(runId)}/cancel`,
    { method: "POST" },
  );
}

export async function approveQueryRun(runId: string): Promise<QueryRun> {
  return jsonRequest<QueryRun>(
    `/query-runs/${encodeURIComponent(runId)}/approve`,
    { method: "POST" },
  );
}

export async function recomputeQueryRun(runId: string): Promise<QueryRun> {
  return jsonRequest<QueryRun>(
    `/query-runs/${encodeURIComponent(runId)}/recompute`,
    { method: "POST" },
  );
}

export async function submitFeedback(
  runId: string,
  rating: "positive" | "negative",
  comment?: string,
): Promise<void> {
  await jsonRequest("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      run_id: runId,
      rating,
      comment: comment?.trim() || null,
    }),
  });
}

export function toHistoryItem(run: QueryRun): QueryHistoryItem {
  const started = run.startedAt ? new Date(run.startedAt).getTime() : NaN;
  const completed = run.completedAt ? new Date(run.completedAt).getTime() : NaN;
  return {
    id: run.id,
    question: run.question,
    status: run.status,
    createdAt: run.startedAt ?? new Date().toISOString(),
    durationMs:
      Number.isFinite(started) && Number.isFinite(completed)
        ? Math.max(0, completed - started)
        : undefined,
  };
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

export async function streamQueryEvents(
  runId: string,
  {
    signal,
    lastEventId = 0,
    onEvent,
    onReconnect,
    reconnectDelayMs = 750,
  }: StreamOptions,
): Promise<void> {
  let cursor = lastEventId;
  let attempt = 0;
  while (!signal.aborted) {
    try {
      const token = await getAccessToken();
      const headers = new Headers({
        Authorization: `Bearer ${token}`,
        Accept: "text/event-stream",
      });
      if (cursor > 0) headers.set("Last-Event-ID", String(cursor));
      const response = await fetch(
        `${API_BASE_URL}/query-runs/${encodeURIComponent(runId)}/events?after_id=${cursor}`,
        { headers, signal, cache: "no-store" },
      );
      if (response.status === 401) {
        await getAccessToken(true);
        throw new ApiError("SSE authentication was refreshed", 401);
      }
      if (!response.ok || !response.body) {
        throw new ApiError(
          `SSE connection failed (${response.status})`,
          response.status,
        );
      }
      let ended = false;
      for await (const frame of readSSEFrames(response.body, signal)) {
        if (frame.event === "stream_end") {
          ended = true;
          break;
        }
        if (frame.id) cursor = Math.max(cursor, Number(frame.id) || cursor);
        await onEvent(parseEventPayload(frame));
      }
      if (ended) return;
      throw new Error("SSE stream closed before a terminal event");
    } catch (error) {
      if (
        signal.aborted ||
        (error instanceof DOMException && error.name === "AbortError")
      ) {
        throw error;
      }
      if (error instanceof AuthenticationRequiredError) throw error;
      if (
        error instanceof ApiError &&
        error.status >= 400 &&
        error.status < 500 &&
        ![401, 408, 429].includes(error.status)
      ) {
        throw error;
      }
      attempt += 1;
      onReconnect?.(attempt);
      await wait(
        Math.min(reconnectDelayMs * 2 ** (attempt - 1), 8_000),
        signal,
      );
    }
  }
}
