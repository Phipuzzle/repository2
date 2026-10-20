export type QueryRunStatus =
  | "idle"
  | "submitting"
  | "streaming"
  | "awaiting_clarification"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "cancelled";

export type QueryEventType =
  | "submitted"
  | "intent_detected"
  | "context_retrieved"
  | "sql_generated"
  | "sql_validated"
  | "query_started"
  | "result_preview"
  | "chart_spec_ready"
  | "run_completed"
  | "clarification_required"
  | "approval_required"
  | "approval_granted"
  | "query_failed"
  | "run_cancelled"
  | "reconnected";

export interface SSEEvent {
  id: number;
  type: QueryEventType;
  timestamp: string;
  message: string;
  data?: Record<string, unknown>;
}

export interface ChartSpec {
  type: "line" | "bar" | "area";
  title: string;
  xField: string;
  yField: string;
  dataset: Array<Record<string, string | number>>;
}

export interface ResultSchema {
  name: string;
  type: string;
  label: string;
}

export interface QueryResult {
  rows: Array<Record<string, string | number>>;
  schema: ResultSchema[];
  total: number;
}

export interface QueryHistoryItem {
  id: string;
  question: string;
  status: QueryRunStatus;
  createdAt: string;
  durationMs?: number;
}

export interface MetricDefinition {
  name: string;
  definition: string;
  source: string;
  updatedAt: string;
}

export interface QueryRun {
  id: string;
  question: string;
  status: QueryRunStatus;
  events: SSEEvent[];
  sql: string;
  result: QueryResult | null;
  chartSpec: ChartSpec | null;
  insight: string;
  error: string | null;
  clarification: string | null;
  approvalReason: string | null;
  reconnectCount: number;
  startedAt: string | null;
  completedAt: string | null;
}
